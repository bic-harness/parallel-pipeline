# Required Variables

Name                Value                               Description
environment_list    ${workflow.variables.env_list}
service_inputs                                          CSV list: ${svc1.inputs},${svc2,inputs} where inputs variable is set in Collect Metadata step.
variable_inputs                                         CSV with format "variableName:Value" for workflow variables (e.g. to map to infra definitions)
pipeline_name                                           Name of the pipeline to be run for each environment in parallel
api_key             ${secrets.getValue("graphql-api-key")}