RuleSet: AddStratifierGroup(groupN, expression, expression-population, subject-path)

* group[{groupN}].id = "group-{groupN}"
* group[{groupN}].population[initialPopulation].code.coding = $measure-population#initial-population
* group[{groupN}].population[initialPopulation].criteria.expression = {expression}
* group[{groupN}].population[initialPopulation].criteria.language = #text/x-fhir-query
* group[{groupN}].population[initialPopulation].id = "initial-population-identifier"

* group[{groupN}].population[measurePopulation].code.coding = $measure-population#measure-population
* group[{groupN}].population[measurePopulation].criteria.expression = "{expression-population}"
* group[{groupN}].population[measurePopulation].criteria.language = #text/fhirpath
* group[{groupN}].population[measurePopulation].id = "measure-population-identifier"

* group[{groupN}].population[measureObservation].code.coding = $measure-population#measure-observation
* group[{groupN}].population[measureObservation].criteria.expression = "{subject-path}"
* group[{groupN}].population[measureObservation].criteria.language = #text/fhirpath
* group[{groupN}].population[measureObservation].extension[aggregateMethod].valueCode = #unique-count
* group[{groupN}].population[measureObservation].extension[aggregateMethod].url = "http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cqfm-aggregateMethod"
* group[{groupN}].population[measureObservation].extension[criteriaReference].valueString = "measure-population-identifier"
* group[{groupN}].population[measureObservation].extension[criteriaReference].url = "http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cqfm-criteriaReference"
* group[{groupN}].population[measureObservation].id = "measure-observation-identifier"

RuleSet: AddStratifierToGroup(groupN, stratN, expression, code, strat-id)
* group[{groupN}].stratifier[{stratN}].criteria.language = #text/fhirpath
* group[{groupN}].stratifier[{stratN}].criteria.expression = "{expression}"
* group[{groupN}].stratifier[{stratN}].code = http://fhir-data-evaluator/strat/system#{code}
* group[{groupN}].stratifier[{stratN}].id = {strat-id}


RuleSet: AddStratifierToGroupWhere(groupN, stratN, fhirPathSelect, fhirPathWhere, code, strat-id)
* group[{groupN}].stratifier[{stratN}].criteria.language = #text/fhirpath
* group[{groupN}].stratifier[{stratN}].criteria.expression = "{fhirPathSelect}({fhirPathWhere})"
* group[{groupN}].stratifier[{stratN}].code = http://fhir-data-evaluator/strat/system#{code}
* group[{groupN}].stratifier[{stratN}].id = {strat-id}






