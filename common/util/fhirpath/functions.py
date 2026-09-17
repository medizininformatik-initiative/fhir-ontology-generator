import re
from typing import Any, List, Optional, Tuple

from antlr4.ParserRuleContext import ParserRuleContext
from antlr4.tree.Tree import TerminalNode
from fhir.resources.R4B.element import Element
from fhir.resources.R4B.elementdefinition import (
    ElementDefinition,
    ElementDefinitionBinding,
    ElementDefinitionSlicingDiscriminator,
)
from pydantic import BaseModel, conlist
from typing_extensions import deprecated

from availability.constants.fhir import MII_CDS_PACKAGE_PATTERN
from common.exceptions import NotFoundError, UnsupportedError
from common.model.fhir.nav_element_definition import NavElementDefinition
from common.model.fhir.nav_structure_definition import (
    NavStructureDefinition,
    ensure_struct_def_is_navigable,
)
from common.model.fhir.structure_definition import (
    StructureDefinitionSnapshot,
)
from common.util.fhir.package.manager import FhirPackageManager
from common.util.fhirpath import RULE_NAMES, fhirpathParser, get_rule_name
from common.util.http.exceptions import ClientError
from common.util.http.terminology.client import FhirTerminologyClient
from common.util.log.functions import get_logger
from common.util.structure_definition.functions import get_parent_element

_logger = get_logger(__file__)

_REGEX_MATCH_TRAILING_WHERE_FUNC = re.compile(r"where\((.*)\)$")
_REGEX_MATCH_TRAILING_EXISTS_FUNC = re.compile(r"exists\((.*)\)$")

# Types `memberOf()` can actually be evaluated against -- Pathling only supports `Coding`/`CodeableConcept` there
_MEMBER_OF_CAPABLE_TYPES = {"Coding", "CodeableConcept"}

ALL_FHIR_RESOURCE_TYPES_R4B = {
    "ChargeItem",
    "StructureMap",
    "DocumentManifest",
    "Group",
    "AdverseEvent",
    "PractitionerRole",
    "ValueSet",
    "OperationOutcome",
    "Account",
    "MessageHeader",
    "Ingredient",
    "Linkage",
    "Condition",
    "SpecimenDefinition",
    "Medication",
    "GraphDefinition",
    "CoverageEligibilityResponse",
    "StructureDefinition",
    "DocumentReference",
    "SupplyRequest",
    "Invoice",
    "RegulatedAuthorization",
    "Appointment",
    "DeviceRequest",
    "Practitioner",
    "PaymentReconciliation",
    "CoverageEligibilityRequest",
    "RequestGroup",
    "Encounter",
    "Endpoint",
    "EnrollmentRequest",
    "ResearchElementDefinition",
    "DeviceMetric",
    "ActivityDefinition",
    "DeviceUseStatement",
    "Task",
    "Claim",
    "Slot",
    "DomainResource",
    "CapabilityStatement",
    "Flag",
    "ImmunizationEvaluation",
    "MeasureReport",
    "EnrollmentResponse",
    "VisionPrescription",
    "Evidence",
    "MedicationStatement",
    "ImplementationGuide",
    "QuestionnaireResponse",
    "Contract",
    "Media",
    "TestScript",
    "Consent",
    "CatalogEntry",
    "Coverage",
    "ConceptMap",
    "Provenance",
    "ResearchSubject",
    "ResearchDefinition",
    "NutritionProduct",
    "Observation",
    "RiskAssessment",
    "OperationDefinition",
    "ClinicalImpression",
    "PaymentNotice",
    "Procedure",
    "Patient",
    "ClaimResponse",
    "Basic",
    "InsurancePlan",
    "CodeSystem",
    "ClinicalUseDefinition",
    "CareTeam",
    "Subscription",
    "MedicationDispense",
    "SubscriptionStatus",
    "CommunicationRequest",
    "PlanDefinition",
    "ServiceRequest",
    "EvidenceReport",
    "DiagnosticReport",
    "Resource",
    "CarePlan",
    "CompartmentDefinition",
    "SubstanceDefinition",
    "Goal",
    "GuidanceResponse",
    "Measure",
    "AllergyIntolerance",
    "PackagedProductDefinition",
    "BodyStructure",
    "NutritionOrder",
    "BiologicallyDerivedProduct",
    "Location",
    "VerificationResult",
    "Composition",
    "EvidenceVariable",
    "MedicationRequest",
    "OrganizationAffiliation",
    "ManufacturedItemDefinition",
    "MedicationAdministration",
    "HealthcareService",
    "Binary",
    "MessageDefinition",
    "ObservationDefinition",
    "List",
    "MolecularSequence",
    "ResearchStudy",
    "Schedule",
    "Person",
    "Communication",
    "EpisodeOfCare",
    "Device",
    "AdministrableProductDefinition",
    "NamingSystem",
    "AppointmentResponse",
    "Questionnaire",
    "SubscriptionTopic",
    "ImmunizationRecommendation",
    "TestReport",
    "ImagingStudy",
    "Substance",
    "Citation",
    "ChargeItemDefinition",
    "Organization",
    "MedicinalProductDefinition",
    "SearchParameter",
    "ExampleScenario",
    "DeviceDefinition",
    "Immunization",
    "Specimen",
    "MedicationKnowledge",
    "RelatedPerson",
    "EventDefinition",
    "AuditEvent",
    "Bundle",
    "Library",
    "SupplyDelivery",
    "Parameters",
    "TerminologyCapabilities",
    "ExplanationOfBenefit",
    "FamilyMemberHistory",
    "DetectedIssue",
}


def fhirpath_filter_for_profile_discriminated_slice(
    slice_elem_def: NavElementDefinition,
    discr_path: str,
    _criteria_only: bool = False,
) -> str:
    """
    Creates a FHIRPath filter expression for the provided profile-discriminated slice element definition

    :param slice_elem_def: Slice-defining element definition
    :param discr_path: Slicing discriminator path
    :param _criteria_only: If `True` only the criteria within the `where()` function invocation are returned
    :return: FHIRPath filter expression string. The filter expression will be a `where` function invocation containing
             the filter criteria that shall be called on the discriminated element
    """
    # Handle 'resolve()' invocation
    ref_elem_rel_path = discr_path.removesuffix("resolve()").removesuffix(".")
    ref_elem_rel_path = ref_elem_rel_path if ref_elem_rel_path else "$this"
    if ref_elem_rel_path == "$this":
        target_elem_def = slice_elem_def
    else:
        target_elem_def = slice_elem_def.child(*ref_elem_rel_path.split("."))
        if not target_elem_def:
            raise ValueError(
                f"Profile-discriminated element definition '{slice_elem_def.id}' has no sub element definition "
                f"'{slice_elem_def.id}.{ref_elem_rel_path}'"
            )
    if not target_elem_def.type:
        raise ValueError(
            f"Profile-discriminated target element definition '{target_elem_def.id}' defines no types"
        )
    exprs = []
    for t in target_elem_def.type:
        # TODO: We might have to adjust this check to include 'targetProfile' when we support Reference/canonical
        if not t.profile and not t.targetProfile:
            raise ValueError(
                f"Profile-discriminated target element definition '{target_elem_def.id}' supports type without profile"
            )
        match t.code:
            case "Extension":
                exprs.append(" or ".join(f"url = '{pr}'" for pr in t.profile))
            case _:
                raise NotImplementedError(
                    f"Cannot generate FHIRPath filter expression for element definition '{slice_elem_def.id}'. Type "
                    f"'{t.code}' is currently not supported in profile discriminated slices"
                )
    match exprs:
        case []:
            raise Exception(
                f"Failed to generate FHIRPath filter expression for profile discriminated element definition "
                f"'{slice_elem_def.id}'"
            )
        case [x]:
            expr = x
        case _:
            expr = " or ".join(exprs)
    if discr_path != "$this":
        expr = f"{discr_path}.{expr}"
    return expr if _criteria_only else f"where({expr})"


def fhirpath_filter_for_type_discriminated_slice(
    slice_elem_def: NavElementDefinition,
    discr_path: str,
    _criteria_only: bool = False,
) -> str:
    if not slice_elem_def.type:
        raise ValueError(
            f"Type-discriminated element definition '{slice_elem_def.id}' defines no types"
        )
    slicing_def_elem_def = slice_elem_def.parent
    if (
        slicing_def_elem_def.type
        and len(slicing_def_elem_def.type) == 1
        and slicing_def_elem_def.type[0].code == "Reference"
    ):
        # If the slicing-defining element definition supports only the data type 'Reference' then the type
        # discriminator is applied to the resource type of the reference target
        target_types = []
        for t_pr in slice_elem_def.type[0].targetProfile:
            res_type = t_pr.removeprefix("http://hl7.org/fhir/StructureDefinition/")
            if res_type not in ALL_FHIR_RESOURCE_TYPES_R4B:
                raise ValueError(
                    f"Type-discriminated element definition '{slice_elem_def.id}' supports target profile "
                    f"'{t_pr}' which does not define a valid FHIR R4B resource type"
                )
            target_types.append(res_type)
        match target_types:
            case []:
                raise Exception(
                    f"Failed to generate FHIRPath filter expression for type-discriminated element "
                    f"definition '{slice_elem_def.id}'"
                )
            case [t]:
                expr = f"resolve() is {t}"
            case _ as ts:
                expr = f"resolve().exists({' or '.join('$this is ' + t for t in ts)})"
        if discr_path != "$this":
            expr = f"{discr_path}.{expr}"
    else:
        types = [t.code for t in slice_elem_def.type]
        if len(types) == 1:
            expr = f"{discr_path} is {types[0]}"
        else:
            expr = " or ".join(f"$this is {t}" for t in types)
            if discr_path != "$this":
                expr = f"{discr_path}.exists({expr})"
    return expr if _criteria_only else f"where({expr})"


def fhirpath_filter_for_exists_discriminated_slice(
    discr_path: str,
    _criteria_only: bool = False,
) -> str:
    expr = "exists()" if discr_path == "$this" else f"{discr_path}.exists()"
    return expr if _criteria_only else f"where({expr})"


def fhirpath_filter_for_value_or_pattern_discriminated_slice(
    slice_elem_def: NavElementDefinition,
    discr_path: str,
    _criteria_only: bool = False,
    manager: Optional[FhirPackageManager] = None,
    client: Optional[FhirTerminologyClient] = None,
) -> str:
    if not slice_elem_def.type:
        raise ValueError(
            f"Value or pattern discriminated element definition '{slice_elem_def.id}' defines no types"
        )

    # Extension shortcut
    if (
        len(slice_elem_def.type) == 1
        and slice_elem_def.type[0].code == "Extension"
        and discr_path == "url"
    ):
        return fhirpath_filter_for_profile_discriminated_slice(
            slice_elem_def, "$this", _criteria_only
        )

    # The full id of the element the discriminator specifies.
    # Cant be computed inside the function because of recursion.
    binding_target_id = (
        slice_elem_def.id
        if discr_path == "$this"
        else f"{slice_elem_def.id}.{discr_path}"
    )
    expr = fhirpath_filter_from_value_discriminated_elem_def(
        slice_elem_def,
        slice_elem_def.struct_def,
        "$this",
        client=client,
        manager=manager,
        _binding_target_id=binding_target_id,
    )
    if not expr:
        raise Exception(
            f"Failed to generate FHIRPath filter expression for value/pattern discriminated element "
            f"definition '{slice_elem_def.id}'"
        )
    return expr.removeprefix("where(").removesuffix(")") if _criteria_only else expr


def fhirpath_filter_for_slice(
    slice_elem_def: NavElementDefinition,
    manager: Optional[FhirPackageManager] = None,
    client: Optional[FhirTerminologyClient] = None,
) -> str:
    parent_elem_def = slice_elem_def.parent
    discriminators = (
        parent_elem_def.slicing.discriminator
        if parent_elem_def and parent_elem_def.slicing
        else []
    )
    if not discriminators:
        raise ValueError(
            f"Parent element definition '{parent_elem_def.id}' defines no slicing discriminators"
        )
    exprs = []
    # A "value"/"pattern" discriminator always resolves to the same combined expression regardless of which
    # specific path it names (see `fhirpath_filter_for_value_or_pattern_discriminated_slice`), so only the first
    # such discriminator needs to be evaluated -- evaluating every one would just AND that identical expression
    # with itself once per discriminator
    value_or_pattern_expr_added = False
    for discr in discriminators:
        if discr.path == "$this":
            norm_discr_path = "$this"
        else:
            norm_discr_path = discr.path.replace("$this.", "")
            # In case absolute paths are used
            if norm_discr_path.startswith(slice_elem_def.path):
                norm_discr_path = norm_discr_path[len(slice_elem_def.path) + 1 :]
            # Some IGs (e.g. MII's imaging extensions) name the discriminator path after the very element the
            # slicing is declared on (e.g. slicing `CodeableConcept.coding` by value with `path: "coding"`). Since
            # that element's own path segment can't be a sub path of itself, this is a self-referential quirk that
            # means the same thing as "$this" -- the whole item is the discriminating value
            elif norm_discr_path == parent_elem_def.path.rsplit(".", 1)[-1]:
                norm_discr_path = "$this"
        # if "resolve()" in norm_discr_path:
        #    raise NotImplementedError(
        #        f"Crossing of resource boundaries via 'resolve()' is currently not supported"
        #    )
        match discr.type:
            case "value" | "pattern":
                if not value_or_pattern_expr_added:
                    exprs.append(
                        fhirpath_filter_for_value_or_pattern_discriminated_slice(
                            slice_elem_def,
                            norm_discr_path,
                            _criteria_only=True,
                            manager=manager,
                            client=client,
                        )
                    )
                    value_or_pattern_expr_added = True
            case "exists":
                exprs.append(
                    fhirpath_filter_for_exists_discriminated_slice(
                        norm_discr_path, _criteria_only=True
                    )
                )
            case "type":
                exprs.append(
                    fhirpath_filter_for_type_discriminated_slice(
                        slice_elem_def, norm_discr_path, _criteria_only=True
                    )
                )
            case "profile":
                exprs.append(
                    fhirpath_filter_for_profile_discriminated_slice(
                        slice_elem_def, norm_discr_path, _criteria_only=True
                    )
                )
            case _ as invalid_type:
                raise ValueError(
                    f"Unknown discriminator type '{invalid_type}' in slicing definition of element "
                    f"definition '{parent_elem_def.id}'"
                )
    return f"where({' and '.join(exprs)})"


def unsupported_fhirpath_expr(
    c: ParserRuleContext,
    expected: str | conlist(str, min_length=1),
    cause: Optional[Exception] = None,
) -> ValueError:
    """
    Builds a `ValueError` instance indicating that a given FHIRPath expression might be valid but is not supported

    :param c: Current parse tree root node, i.e. the parsed expression
    :param expected: Expected values, types, or properties
    :param cause: Optional cause to append to the error message
    :return: `ValueError` instance
    """
    match expected:
        case str():
            expected_str = f"Expected {expected}."
        case list():
            expected_str = (
                "Expected one of {" + ",".join([f"'{s}'" for s in expected]) + "}."
            )
        case _:
            expected_str = ""
    err = ValueError(
        f"Unsupported {get_rule_name(c)} expression in FHIRPath expression @ [{c.start.start}, {c.stop.stop}]: "
        f"{expected_str} Expression: {c.toStringTree(ruleNames=RULE_NAMES)}"
    )
    if cause:
        err.__cause__ = cause
    return err


def invalid_fhirpath_expr(
    c: ParserRuleContext, reason: str, cause: Optional[Exception] = None
) -> ValueError:
    """
    Builds a `ValueError` instance indicating that the provided FHIRPath expression is invalid

    :param c: Current parse tree root node, i.e. the parsed expression
    :param reason: Reason why the expression is deemed invalid
    :param cause: Optional, underlying cause (e.g. raised `Exception` instance indicating that the expression is
                  invalid)
    :return: `ValueError` instance
    """
    err = ValueError(
        f"Invalid {get_rule_name(c)} expression in FHIRPath expression @ [{c.start.start}, {c.stop.stop}]: {reason}. "
        f"Expression: {c.toStringTree(ruleNames=RULE_NAMES)}"
    )
    if cause:
        err.__cause__ = cause
    return err


def get_symbol(expr: ParserRuleContext, strip: bool = True) -> Optional[str]:
    """
    Retrieves the symbol of the given (nested) expression

    :param expr:
    :param strip: If `True` removes leading and trailing quotes
    :return:
    """
    while not isinstance(expr, TerminalNode):
        match expr.getChildCount():
            case 1:
                expr = expr.getChild(0)
            case _:
                return None
    return expr.symbol.text.strip("'") if strip else expr.symbol.text


def get_path(expr: ParserRuleContext) -> (Optional[ParserRuleContext], Optional[str]):
    """
    Retrieves the largest, uninterrupted subexpression representing pure element navigation starting at the end of the
    expression without function invocations

    :param expr: Parsed FHIRPath expression
    :return: Tuple containing the remaining expression after an interruption and the path navigation subexpression. Both
             can be `None` depending on the structure of the provided expression
    """
    path = []
    while not isinstance(expr.getChild(2), fhirpathParser.FunctionInvocationContext):
        match expr:
            case fhirpathParser.InvocationExpressionContext() as iec:
                match iec.getChild(2):
                    case fhirpathParser.MemberInvocationContext() as mic:
                        path.append(get_symbol(mic))
                    case _ as c:
                        raise unsupported_fhirpath_expr(c, "member invocation")
                expr = expr.getChild(0)
            case fhirpathParser.TermExpressionContext() as tec:
                path.append(get_symbol(tec))
                expr = None
                break
            case fhirpathParser.MemberInvocationContext() as mic:
                path.append(get_symbol(mic))
            case _:
                break
    path.reverse()
    return expr, ".".join(path) if path else None


def join_fhirpath(*paths: str | None) -> str:
    """
    Joins individual FHIRPath expression strings together. `None` values, empty strings, and '$this' valued strings are
    ignored

    :param paths: List of FHIRPath expression strings
    :return: String of joined FHIRPath expressions or '$this' if none are provided
    """
    string = ".".join(
        filter(lambda x: x is not None and len(x) > 0 and x != "$this", paths)
    )
    return string if len(string) > 0 else "$this"


def _find_polymorphic_value(data: Element, element_name: str) -> Optional[Any]:
    """
    Attempts to find the value of a polymorphic element by iterating over all possible data type-specific names

    :param data: FHIR structure to find the value of a contained polymorphic element in
    :param element_name: (Typeless) name of the polymorphic element in the structure
    :return: Value of the contained element or `None` if no such element exists/it has no value
    """
    for field_name in data.__class__.model_fields.keys():
        if field_name.startswith(element_name):
            v = getattr(data, field_name)
            if v:
                return v
    return None


def _find_value_for_discriminator_pattern_or_value(
    elem: ElementDefinition,
) -> Optional[Tuple[str, Any]]:
    """
    Attempts to find the discriminator value of a slice-defining FHIR element definition for pattern or value
    discriminated slicings, e.g. looks for a values in the `fixed[x]`, `pattern[x]`, or `binding` sub-element

    :param elem: `ElementDefinition` instance containing the discriminator value
    :return: Tuple of the value type (``"fixed"``, ``"pattern"``, or ``"binding"``) and the value or `None` if the
             element definition defines has none of these restrictions
    """
    if fixed := _find_polymorphic_value(elem, "fixed"):
        return "fixed", fixed
    if pattern := _find_polymorphic_value(elem, "pattern"):
        return "pattern", pattern
    if elem.binding:
        return "binding", elem.binding
    return None


def _element_data_to_fhirpath_filter(key: str = "$this", data: Any = None) -> List[str]:
    """
    Recursively traverses a FHIR element data and depending on its basic structure (e.g. it being a simple value, list,
    or key-value-mapping) translates its content into a FHIRPath expression filter in the form of a 'where' function
    invocation. Used internally by the `_element_to_fhirpath_filter` function

    :param key: Name of the element in its parent structure
    :param data: FHIR element data to transform
    :return: List of FHIRPath filter string
    """
    exprs = []
    match data:
        case dict():
            sub_exprs = [
                e
                for k, v in data.items()
                for e in _element_data_to_fhirpath_filter(k, v)
            ]
            match len(sub_exprs):
                case 0:
                    pass
                case 1:
                    expr = sub_exprs[0]
                    if key == "$this":
                        exprs.append(expr)
                    else:
                        if _REGEX_MATCH_TRAILING_EXISTS_FUNC.search(expr):
                            exprs.append(f"{key}.{expr}")
                        else:
                            exprs.append(f"{key}.exists({expr})")
                case _:
                    if key == "$this":
                        exprs.extend(sub_exprs)
                    else:
                        exprs.append(f"{key}.exists({' and '.join(sub_exprs)})")
        case list():
            sub_exprs = [
                e for v in data for e in _element_data_to_fhirpath_filter(data=v)
            ]
            match len(sub_exprs):
                case 0:
                    pass
                case 1:
                    expr = sub_exprs[0]
                    exprs.append(f"{key}.exists({expr})" if key != "$this" else expr)
                case _:
                    clause = (
                        [f"{key}.exists({' and '.join(sub_exprs)})"]
                        if key != "$this"
                        else sub_exprs
                    )
                    exprs.extend(clause)
        case _:
            # TODO: Add handling for other simple FHIR data types
            exprs.append(f"{key} = '{str(data)}'")
    return exprs


def _element_to_fhirpath_filter(key: str = "$this", elem: Any = None) -> str:
    """
    Recursively traverses a FHIR element and depending on its basic structure (e.g. it being a simple value, list, or
    key-value-mapping) translates its content into a FHIRPath expression filter in the form of a 'where' function
    invocation

    :param key: Name of the element in its parent structure
    :param elem: FHIR element to transform
    :return: FHIRPath filter string
    """
    if isinstance(elem, Element):
        elem_data = elem.model_dump(exclude_none=True, exclude_unset=True)
    else:
        elem_data = elem
    clause = " and ".join(_element_data_to_fhirpath_filter(key, elem_data))
    return f"where({clause})"


def _fhirpath_where_predicate(where_filter: str) -> str:
    """
    Extracts the predicate from a FHIRPath where invocation.
    """
    if match := _REGEX_MATCH_TRAILING_WHERE_FUNC.search(where_filter):
        return match.group(1)
    return where_filter


def _append_filter_from_profile_discriminated_elem(
    base_expr: str,
    elem: ElementDefinition,
    discr: ElementDefinitionSlicingDiscriminator,
    snapshot: StructureDefinitionSnapshot,
    manager: FhirPackageManager,
    package_pattern: dict = MII_CDS_PACKAGE_PATTERN,
) -> str:
    """
    Appends a FHIRPath filter based on the constraints of a profile discriminated slice to the given FHIRPath
    expression. ATM, only elements of type `canonical`, `Reference`, or `Extension` are supported

    :param base_expr: FHIRPath expression to add the slice-based filter to
    :param elem: `ElementDefinition` representing element targeted by discriminator
    :param discr: Slicing discriminator
    :param snapshot: Structure Definition snapshot containing the discriminated element
    :param manager: FHIR package manager providing access to package cache
    :param package_pattern: Package index pattern used to resolve dependent profiles
    :return: Extended FHIRPath expression
    """
    types = elem.type
    if len(types) > 1:
        raise ValueError(
            f"Profile discriminated element '{elem.id} in profile '{snapshot.url}' supports more than one type"
        )
    t = types[0]
    match t.code:
        case "Reference" | "canonical":
            target_profile_urls = t.targetProfile
            clause = " or ".join(
                [
                    f"$this = '{url}'"
                    for target_profile_url in target_profile_urls
                    for url in [
                        target_profile_url,
                        *[
                            p.url
                            for p in manager.dependents_of(
                                target_profile_url, package_pattern
                            )
                        ],
                    ]
                ]
            )
            # Make path relative to discriminated element (apparently absolute resource paths are allowed as
            # discriminator paths)
            path = discr.path.removeprefix(f"{base_expr}.")
            # Remove (possible) trailing resolve function call
            path = re.sub(r"\.?resolve\(\)$", "", path)
            return f"{base_expr}.where({path + '.' if path else ''}resolve().meta.profile.exists({clause}))"
        case "Extension":
            if len(t.profile) == 1:
                return f"{base_expr}('{t.profile[0]}')"
            clause = " or ".join([f"url = '{url}'" for url in t.profile])
            # expr = clause if discr.path == "$this" else f"{discr.path}.exists({clause})"
            return f"{base_expr}.where({clause})"
        case _:
            raise UnsupportedError(
                f"Type '{t.code}' is currently not supported in profile discriminated "
                f"elements [element_id='{elem.id}', profile_url='{snapshot.url}']"
            )


def _valueset_codes_filter(target: str, codes: List[str]) -> str:
    """
    Creates FHIRPath filter from a list of codes

    :param target: `"$this"` if `target` itself is what should be tested, otherwise the (relative) path to test
    :param codes: List of possible codes
    :return: FHIRPath filter expression string
    """
    if len(codes) == 1:
        return f"{target} = '{codes[0]}'"
    alternatives = " or ".join(f"$this = '{c}'" for c in codes)
    return (
        f"{target}.exists({alternatives})" if target != "$this" else f"({alternatives})"
    )


def _filter_from_binding(
    elem_def: NavElementDefinition,
    target: str,
    client: Optional[FhirTerminologyClient],
) -> Optional[str]:
    """
    Builds a FHIRPath filter expression testing `target` against the ValueSet bound to `elem_def`.

    `memberOf()` is only used when `elem_def` is `Coding`/`CodeableConcept`-typed
    For any other type the ValueSet is expanded instead and the filter lists the allowed codes explicitly.

    :param elem_def: Element definition the binding is declared on
    :param binding: The binding itself
    :param target: `"$this"` if `elem_def` itself is what should be tested, otherwise the (relative) path to test
    :param client: FHIR terminology client used to expand the ValueSet
    :return: FHIRPath filter expression string, or `None` if none could be built
    """
    binding: ElementDefinitionBinding = elem_def.binding
    if client is None or any(
        t.code in _MEMBER_OF_CAPABLE_TYPES for t in (elem_def.type or [])
    ):
        return f"{target}.memberOf('{binding.valueSet}')".replace("$this.", "")
    try:
        expansion = client.expand_value_set(url=binding.valueSet)
        codes = [
            c["code"]
            for c in (expansion or {}).get("expansion", {}).get("contains", [])
            if c.get("code")
        ]
    except ClientError as err:
        _logger.warning(
            f"Could not expand ValueSet '{binding.valueSet}' bound to '{elem_def.id}': {err}"
        )
        return None
    if not codes:
        return None
    return _valueset_codes_filter(target, codes)


def fhirpath_retrieve_children_of_type_profile(
    profile_url: str, manager: FhirPackageManager
) -> List[NavElementDefinition]:
    """
    Extracts all direct children of the root element of the target type profile. Useful if the elements needed to
    build a slice discriminator filter, are defined on the type profile itself rather than locally on the sliced
    element.
    :param profile_url: Url of the type profile
    :param manager: Package-manager for retrieving the profile
    :return: List of the root element's direct child NavElementDefinitions
    """

    if not (type_profile := manager.find_struct_def(profile_url)):
        raise NotFoundError(f"Type-Profile with url {profile_url} not found")

    if not (base_el_id := type_profile.type):
        raise NotFoundError(
            f"Type-Profile with url {profile_url} does not contain element with type-profile.type as id"
        )

    base_el: NavElementDefinition | None = type_profile.get_element_by_id(base_el_id)
    if not base_el:
        raise NotFoundError(
            f"Root element '{type_profile.type}' not found in Type-Profile '{profile_url}'"
        )

    return base_el.elements


def fhirpath_filter_from_value_discriminated_elem_def(
    elem_def: NavElementDefinition,
    struct_def: NavStructureDefinition,
    discr_path: Optional[str] = None,
    client: Optional[FhirTerminologyClient] = None,
    manager: FhirPackageManager = None,
    _binding_target_id: Optional[str] = None,
) -> Optional[str]:
    """
    Creates a FHIRPath filter expression for the provided value-discriminated element definition

    :param elem_def: element definition to which a value-type discriminator path points
    :param struct_def: structure definition holding the element definition
    :param discr_path: Discriminator path. Providing `None` is intended for internal use
    :param _binding_target_id: The element id the discriminator actually points to. Only here a binding is and considered
    :return: FHIRPath filter expression string or `None` if not expression could be determined
    """
    exprs = []
    is_binding_target = _binding_target_id is None or elem_def.id == _binding_target_id

    if ret := _find_value_for_discriminator_pattern_or_value(elem_def):
        discr_value_type, discr_value = ret
        if discr_value_type == "binding":
            # a binding is only trusted on the element the discriminator specifies: binding_target_id
            if is_binding_target and discr_value.valueSet:
                binding_expr = _filter_from_binding(
                    elem_def, "$this" if discr_path else elem_def.rel_path, client
                )
                if discr_value.strength == "required":
                    exprs.append(binding_expr)
        else:
            exprs.extend(
                _element_data_to_fhirpath_filter(
                    key="$this" if discr_path else elem_def.rel_path,
                    data=(
                        discr_value.model_dump()
                        if isinstance(discr_value, BaseModel)
                        else discr_value
                    ),
                )
            )

    # store, if exprs come from this element or from its children. Second case needs this's elements name as a prefix
    found_directly_on_elem_def = bool(exprs)

    if not exprs:
        # We ignore slices since the discriminator value should be part of any instance of the element. Checking the
        # element definitions within the structure definition snapshot should suffice since the discriminator value will be
        # defined by it

        children = elem_def.elements

        # case when slice discr info is in type profile
        # This should only be used when elem_def.elements has no elements, to avoid a filter with duplicate entries
        if (
            len(elem_def.elements) == 0
            and manager
            and elem_def.type
            and elem_def.type[0].profile
            and len(elem_def.type[0].profile) == 1
            and (type_profile_url := elem_def.type[0].profile[0])
        ):
            children = fhirpath_retrieve_children_of_type_profile(
                type_profile_url, manager
            )

        for sub_elem in children:
            if sub_elem_expr := fhirpath_filter_from_value_discriminated_elem_def(
                sub_elem,
                struct_def,
                manager=manager,
                client=client,
                _binding_target_id=_binding_target_id,
            ):
                exprs.append(sub_elem_expr)

    add_discr_path = discr_path is not None and discr_path != "$this"
    match exprs:
        case []:
            return None
        case [x]:
            if discr_path is None and not found_directly_on_elem_def:
                return f"{elem_def.rel_path}.{x}"
            # Wrap with `where` function invocation on non-internal call to produce final FHIRPath filter expression
            return (
                f"where({(discr_path + '.') if add_discr_path else ''}{x})".replace(
                    ".$this", ""
                )
                if discr_path
                else x
            )
        case _:
            join = " and ".join(exprs)
            # if the fhir path expression is found directly on the current element, its name has to be added as a prefix
            if discr_path is None and not found_directly_on_elem_def:
                return f"{elem_def.rel_path}.exists({join})"
            criteria = f"{discr_path}.exists({join})" if add_discr_path else join
            return f"where({criteria})".replace(".$this", "")


def _find_discr_value_defining_elem_def(
    discr_path: str,
    snapshot: StructureDefinitionSnapshot,
    root_elem_def: Optional[ElementDefinition] = None,
) -> ElementDefinition:
    """
    Follows the discriminator path and at each node check for the discriminator value in the element at the current
    sub path. The discriminator value can be defined in any element definition whos path is a sub path of the
    discriminator path. For instance, given the discriminator defined on element with path 'a.b.c' and discriminator
    path `d.e.f`, we have to check elements 'a.b.c', `a.b.c.d`, ..., and `a.b.c.d.e.f`. If the path is not exhausted, we
    expect the value of an element to be complex and the rest of the path being represented in the structure of its
    value

    :param discr_path: Path to the discriminator value-defining element
    :param snapshot: `StructureDefinition` snapshot defining the element
    :param root_elem_def: Root element definition from which to start the search, i.e. at which the discriminator path
                          should be evaluated. Can for instance be the slicing-defining element definition. If `None`
                          the resource root will be used as a starting point
    :return: `ElementDefinition` instance containing the value definition
    """
    if not root_elem_def:
        root_elem_def = snapshot.get_element_by_id(snapshot.type)
    elem_def = root_elem_def

    def get_val(path: List[str], data: Any) -> Optional[Any]:
        try:
            v = data
            for name in path:
                v = getattr(data, name)
            return v
        except AttributeError:
            return None

    chain = list(filter(len, discr_path.removeprefix("$this.").split(".")))
    slice_name = elem_def.sliceName
    while len(chain) > 0:
        ret = _find_value_for_discriminator_pattern_or_value(elem_def)
        if ret is not None:
            _, val = ret
            # Skip if the eligible element is a value set binding as long as it is defined on elements that
            # represent intermediate nodes of the discriminator path
            if (
                not isinstance(val, ElementDefinitionBinding)
                and get_val(chain, val) is not None
            ):
                break
        discr_elem_def_id = f"{elem_def.id}.{chain.pop(0)}"
        if discr_elem_def := snapshot.get_element_by_id(discr_elem_def_id):
            elem_def = discr_elem_def
        else:
            raise NotFoundError(
                f"Missing value-defining element definition '{discr_elem_def_id}' for slice '{slice_name}' in "
                f"profile '{snapshot.url}' => Cannot generate filter"
            )
    return elem_def


def _get_filter_from_pattern_or_value_discriminated_elem(
    elem_def: ElementDefinition,
    discr_path: str,
    snapshot: StructureDefinitionSnapshot,
    manager: FhirPackageManager,
) -> str:
    """
    Follows the discriminator path and at each node check for the discriminator value in the element at the current
    sub path. The discriminator value can be defined in any element definition whose path is a sub path of the
    discriminator path. For instance, given the discriminator defined on element with path 'a.b.c' and discriminator
    path `d.e.f`, we have to check elements 'a.b.c', `a.b.c.d`, ..., and `a.b.c.d.e.f`. If the path is not exhausted, we
    expect the value of an element to be complex and the rest of the path being represented in the structure of its
    value

    :param elem_def: `ElementDefinition` instance where a slice is defined
    :param discr_path: (Relative) path to the discriminator value
    :param snapshot: Snapshot containing the element definition
    :param manager: FHIR package manager providing access to package cache
    :return: FHIRPath filter selecting elements matching the slice
    """
    # TODO: Apply navigable structure def model to entire code base
    snapshot = ensure_struct_def_is_navigable(snapshot)
    elem_def = snapshot.get_element_by_id(elem_def.id)
    if "resolve()" in discr_path:
        # If the discriminator path crosses resource boundaries all references will be resolved to find the range of
        # values for slice membership
        split = discr_path.split("resolve()", maxsplit=1)
        pre_resolve, post_resolve = split[0].strip("."), split[1].strip(".")
        ref_elem_def = (
            snapshot.get_element_by_id(f"{elem_def.id}.{pre_resolve}")
            if pre_resolve
            else elem_def
        )
        exprs = []
        for target_profile_url in ref_elem_def.type[0].targetProfile:
            target_profile = manager.find(index_pattern={"url": target_profile_url})
            if not target_profile:
                raise NotFoundError(
                    f"Failed to resolve profile '{target_profile_url}' containing value-defining element "
                    f"'{post_resolve}' for slice '{elem_def.sliceName}' => Cannot generate filter"
                )
            val_elem_def = _find_discr_value_defining_elem_def(
                post_resolve, target_profile
            )
            if discr_val_t := _find_value_for_discriminator_pattern_or_value(
                val_elem_def
            ):
                val_type, value = discr_val_t
                match val_type:
                    case "binding":
                        exprs.append(f"memberOf('{value.valueSet}'))")
                    case _:
                        exprs.append(
                            " and ".join(
                                _element_data_to_fhirpath_filter(
                                    data=value.model_dump()
                                )
                            )
                        )
            else:
                raise NotFoundError(
                    f"Missing any of fixed[x], pattern[x], or binding in element definition '{val_elem_def.id}' of "
                    f"profile '{target_profile_url}' targeted by the discriminator => Cannot generate filter"
                )
        return f"where({(pre_resolve + '.') if pre_resolve else ''}resolve().{post_resolve}.exists({('(' + ' or '.join(exprs) + ')') if len(exprs) != 1 else exprs[0]}))"

    else:
        # The discriminator path is contained within the resource were the slicing is defined
        if discr_path != "$this":
            elem_def = _find_discr_value_defining_elem_def(
                discr_path, snapshot, elem_def
            )
        if discr_filter := fhirpath_filter_from_value_discriminated_elem_def(
            elem_def, snapshot, discr_path, manager=manager
        ):
            return discr_filter
        else:
            raise NotFoundError(
                f"Missing any of fixed[x], pattern[x], or binding in element definition '{elem_def.id}' of profile "
                f"'{snapshot.url}' targeted by the discriminator => Cannot generate filter"
            )


@deprecated("Replaced be fhirpath_filter_for_slice")
def filter_for_slice(
    base_expr: str,
    slice_elem_def: ElementDefinition,
    snapshot: StructureDefinitionSnapshot,
    manager: FhirPackageManager,
    package_pattern: dict = MII_CDS_PACKAGE_PATTERN,
) -> str:
    """
    Appends a slice-based filter part to the given FHIRPath expression

    :param base_expr: FHIRPath expression to base extended expression on
    :param slice_elem_def: Slice-defining `ElementDefinition`
    :param snapshot: Structure definition snapshot contain the sliced element
    :param manager: FHIR package manager
    :param package_pattern: Package index pattern used to resolve profile discriminator dependencies
    :return: Extended version of the given FHIRPath expression
    """
    parent_elem = get_parent_element(snapshot, slice_elem_def)
    discriminators = parent_elem.slicing.discriminator
    exprs: List[str] = []
    if len(discriminators) == 0:
        raise Exception(
            f"Cannot get filter for element '{slice_elem_def.id}'. Parent element '{parent_elem.id}' "
            f"defines no discriminator"
        )
    single_discriminator = len(discriminators) == 1
    for discr in discriminators:
        discr_path = discr.path.replace("$this.", "")
        match discr.type:
            case "value" | "pattern":
                # FIXME: The value discriminator type is pretty much treated like the pattern discriminator type,
                #        though this might not be accurate
                # Both discriminator types support all of these options
                t = slice_elem_def.type[0]
                if t.code == "Extension":
                    # NOTE: There are potentially other ways by which an extension could be discriminated
                    if discr_path != "url":
                        raise UnsupportedError(
                            f"Only pattern or value discriminators targeting an extensions 'url' "
                            f"element are supported to discriminate Extension typed elements "
                            f"[element_id='{slice_elem_def.id}', profile_url='{snapshot.url}']"
                        )
                    if t.profile:
                        checks = []
                        if len(t.profile) == 1:
                            if single_discriminator:
                                return f"{base_expr}('{t.profile[0]}')"
                        for url in t.profile:
                            index_pattern = {"url": url}
                            ext_snapshot = manager.find(index_pattern)
                            url_elem_def = ext_snapshot.get_element_by_id(
                                "Extension.url"
                            )
                            checks.append(f"url = '{url_elem_def.fixedUri}'")
                        exprs.append(f"({' or '.join(checks)})")
                    else:
                        where_filter = (
                            _get_filter_from_pattern_or_value_discriminated_elem(
                                slice_elem_def, discr_path, snapshot, manager
                            )
                        )
                        matches = re.findall(r"\'(\S+)\'", where_filter)
                        if single_discriminator and len(matches) == 1:
                            return f"{base_expr}('{matches[0]}')"
                        exprs.append(_fhirpath_where_predicate(where_filter))
                else:
                    exprs.append(
                        _fhirpath_where_predicate(
                            _get_filter_from_pattern_or_value_discriminated_elem(
                                slice_elem_def, discr_path, snapshot, manager
                            )
                        )
                    )
            case "exists":
                exprs.append(f"{discr_path}.exists()")
            case "type":
                if single_discriminator and len(slice_elem_def.type) == 1:
                    expr = f"ofType({slice_elem_def.type[0].code})"
                    type_expr = (
                        expr if discr_path == "$this" else f"{discr_path}.{expr}"
                    )
                    return base_expr + "." + type_expr
                else:
                    clause = " or ".join(
                        [f"$this is {t.code}" for t in slice_elem_def.type]
                    )
                    exprs.append(
                        clause
                        if discr_path == "$this"
                        else f"{discr_path}.exists({clause})"
                    )
            case "profile":
                if discr_path == "$this":
                    target_elem = slice_elem_def
                    target_elem_id = slice_elem_def.id
                else:
                    # Make path relative to discriminated element (apparently absolute resource paths are allowed as
                    # discriminator paths)
                    path = discr_path.removeprefix(f"{slice_elem_def.path}.")
                    # Remove (possible) leading $this selector
                    path = path.removeprefix("$this.")
                    # Remove (possible) trailing resolve function call
                    path = re.sub(r"\.?resolve\(\)$", "", path)
                    target_elem_id = slice_elem_def.id + ("." + path if path else "")
                    target_elem = snapshot.get_element_by_id(target_elem_id)
                if not target_elem:
                    raise NotFoundError(
                        f"Could not find element definition '{target_elem_id}' in profile "
                        f"'{snapshot.url}' representing profile discriminated element"
                    )
                exprs.append(
                    _fhirpath_where_predicate(
                        _append_filter_from_profile_discriminated_elem(
                            base_expr,
                            target_elem,
                            discr,
                            snapshot,
                            manager,
                            package_pattern,
                        )
                    )
                )
            case _ as t:
                raise Exception(
                    f"Unknown discriminator type '{t}' in slicing definition"
                )
    return f"{base_expr}.where({' and '.join(exprs)})"
