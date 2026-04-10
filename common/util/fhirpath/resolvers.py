from abc import ABC
from typing import List, Tuple, TypeVar, Generic, override, Generator, Optional

from fhir.resources.R4B.elementdefinition import ElementDefinition

from common.model.fhir.structure_definition import StructureDefinitionSnapshot
from common.model.fhir.types import validate_fhir_data_type_name_in_version
from common.util.collections.functions import first
from common.util.fhir.package.manager import FhirPackageManager
from common.util.fhirpath import parse_expr, fhirpathParser, get_rule_name, ExternalConstant
from common.util.fhirpath.functions import get_fhirpath_expression_root_node


# Types
T = TypeVar("T", bound=fhirpathParser.InvocationContext)


# Events
class Event(ABC, Generic[T]):
    def __init__(self, invocation: T):
        self._trigger = invocation
        self._process()

    def _process(self):
        pass

    def __repr__(self) -> str:
        member_str = ", ".join([f"{k}={repr(v)}" for k, v in self.__dict__.items() if not k.startswith("_")])
        return self.__class__.__name__ + "(" + member_str + ")"

    @staticmethod
    def for_invocation(invoc: fhirpathParser.InvocationContext):
        match invoc:
            case fhirpathParser.MemberInvocationContext():
                return MemberInvocation(invoc)
            case fhirpathParser.FunctionInvocationContext():
                return FunctionInvocation.for_invocation(invoc)
            case _:
                raise ValueError(f"Unsupported FHIRPath invocation expression [type={get_rule_name(invoc)}, "
                                 f"expr=\"{invoc.getText()}\"]")


class MemberInvocation(Event[fhirpathParser.MemberInvocationContext]):
    @override
    def _process(self):
        self.identifier: str = self._trigger.identifier().getText()


class FunctionInvocation(Event[fhirpathParser.FunctionInvocationContext]):
    def __init__(self, invocation: fhirpathParser.FunctionInvocationContext):
        self.identifier: str = invocation.function().identifier().getText()
        param_list = invocation.function().paramList()
        self._parameters: List[fhirpathParser.ExpressionContext] = param_list.expression() if param_list else []
        super().__init__(invocation)

    @staticmethod
    def for_invocation(invoc: fhirpathParser.FunctionInvocationContext):
        match invoc.function().identifier().getText():
            case "slice":
                return SliceFunctionInvocation(invoc)
            case "resolve":
                return ResolveFunctionInvocation(invoc)
            case "ofType":
                return OfTypeFunctionInvocation(invoc)
            case _ as f_ident:
                raise ValueError(f"Unsupported FHIRPath function '{f_ident}'")


class SliceFunctionInvocation(FunctionInvocation):
    @override
    def _process(self):
        self.structure_ref: str = self._parameters[0].term().getText().strip("'")
        self.slice_name: str = self._parameters[1].term().getText().strip("'")


class ResolveFunctionInvocation(FunctionInvocation):
    pass


class OfTypeFunctionInvocation(FunctionInvocation):
    @override
    def _process(self):
        resource_type = self._parameters[0].term().getText()
        self.type_name: str = validate_fhir_data_type_name_in_version("R4B", resource_type)


def walk_expr(expr: fhirpathParser.ExpressionContext) -> Generator[Event[T], None, None]:
    """
    Walks the provided FHIRPath expression starting at its execution root (not parse tree root) and emits events
    corresponding to encountered expressions (see ``common.util.fhirpath.resolvers.Event[T]``)

    :param expr: Parse tree root node
    :return: Generator yielding traversal events
    """
    root_node = get_fhirpath_expression_root_node(expr)
    # Assume root expression to be of pattern termExpression->invocationTerm->memberInvocation
    if not isinstance(root_node, fhirpathParser.TermExpressionContext):
        raise ValueError(f"Unexpected FHIRPath expression root node type [actual={get_rule_name(root_node)}, "
                         f"expected=termExpression, expr=\"{expr.getText()}\"]")
    member_invoc = root_node.term().invocation()
    yield MemberInvocation(member_invoc)
    # Process parents
    curr_node = root_node.parentCtx
    while isinstance(curr_node, fhirpathParser.InvocationExpressionContext):
        yield Event.for_invocation(curr_node.invocation())
        curr_node = curr_node.parentCtx


def _get_element_def_fuzzy(structure_def: StructureDefinitionSnapshot, element_def_id) -> ElementDefinition:
    if elem_def := structure_def.get_element_by_id(element_def_id):
        return elem_def
    elif elem_def := structure_def.get_element_by_id(element_def_id + "[x]"):
        return elem_def
    else:
        raise KeyError(f"No such element definition [id='{element_def_id}([x])', structure_def='{structure_def.url}']")


# Resolution
class FhirPathResolver:
    def __init__(self, package_manager: FhirPackageManager):
        self.__package_manager = package_manager

    def __process_slice_function(self, event: SliceFunctionInvocation, structure_def: StructureDefinitionSnapshot, slicing_elem_def_id: str) -> Tuple[StructureDefinitionSnapshot, ElementDefinition, str]:
        if event.structure_ref != ExternalConstant.PROFILE and event.structure_ref != structure_def.url:
            structure_def = self.__package_manager.find_snapshot(event.structure_ref)
        elem_def_id = slicing_elem_def_id + ":" + event.slice_name
        elem_def = _get_element_def_fuzzy(structure_def, elem_def_id)
        if len(elem_def.type) == 1:
            # Check if the slice defining element definition has an external content definition, e.g. the elements
            # children are not defined in its structure definition but that of some extension for data type definition.
            # For this to work, the element definition can only support a single data type since the resolution would be
            # ambiguous otherwise
            type_def = elem_def.type[0]
            match type_def.profile:
                case [_, _, *_]:
                    raise Exception(f"Slice definition supports more than one profile for type [elem_def='{elem_def.id}', structure_def='{structure_def.url}']")
                case [profile_url]:
                    return self.__package_manager.find_snapshot(profile_url), elem_def, type_def.code
        return structure_def, elem_def, elem_def_id

    def __process_resolve_function(self, structure_def: StructureDefinitionSnapshot, elem_def: ElementDefinition) -> StructureDefinitionSnapshot:
        type_def = first(lambda t: t.code == "Reference", elem_def.type)
        if not type_def:
            raise Exception(f"Target element definition of resolve call does not support data type 'Reference' [elem_def='{elem_def.id}', structure_def='{structure_def.url}']")
        match type_def.targetProfile:
            case [profile_url]:
                return self.__package_manager.find_snapshot(profile_url)
            case _:
                raise Exception(f"Reference definition is not supporting exactly one profile [elem_def='{elem_def.id}', structure_def='{structure_def.url}']")

    def resolve_path(self, context: StructureDefinitionSnapshot, fhir_path: str) -> List[Tuple[StructureDefinitionSnapshot, ElementDefinition]]:
        """
        Resolves the given FHIRPath expression to element definitions and the structure definitions they are contained
        in order of the path traversal. Each element in the returned chain represents on element entirely contained
        within a single structure definition. Additional links are appended to the chain if

        - A slice defining element definition identified via ``slice()`` function invocation refers to externally defined content, e.g. other profiles
        - A ``resolve()`` function invocation indicates the crossing of resource boundaries

        :param context: Structure definition serving as the context in which to resolve the expression
        :param fhir_path: FHIRPath expression string
        :return: List of structure definition-element definition-pairs
        """
        parsed_expr = parse_expr(fhir_path)
        events = walk_expr(parsed_expr.expression())
        curr_structure_def = context
        curr_elem_def: Optional[ElementDefinition] = None
        chain = []
        # Common case: First event is a member invocation with the resource type as the identifier
        first_event = next(events)
        identifier = first_event.identifier
        curr_elem_def_id = identifier if identifier == curr_structure_def.type else f"{curr_structure_def.type}.{identifier}"
        # Consume remaining events
        for event in events:
            match event:
                case MemberInvocation():
                    curr_elem_def_id += "." + event.identifier
                case FunctionInvocation():
                    match event:
                        case SliceFunctionInvocation():
                            s_sd, s_ed, s_edi = self.__process_slice_function(event, curr_structure_def, curr_elem_def_id)
                            if s_sd.type != curr_structure_def.type and s_sd.url != curr_structure_def.url:
                                chain.append((curr_structure_def, s_ed))
                            curr_structure_def = s_sd
                            curr_elem_def = None
                            curr_elem_def_id = s_edi
                        case ResolveFunctionInvocation():
                            curr_elem_def = _get_element_def_fuzzy(curr_structure_def, curr_elem_def_id)
                            r_sd = self.__process_resolve_function(curr_structure_def, curr_elem_def)
                            chain.append((curr_structure_def, curr_elem_def))
                            curr_structure_def = r_sd
                            curr_elem_def = None
                            curr_elem_def_id = r_sd.type
                        case OfTypeFunctionInvocation():
                            pass # Not yet needed

        if not curr_elem_def or curr_elem_def.id != curr_elem_def_id:
            curr_elem_def = _get_element_def_fuzzy(curr_structure_def, curr_elem_def_id)
            chain.append((curr_structure_def, curr_elem_def))
        return chain
