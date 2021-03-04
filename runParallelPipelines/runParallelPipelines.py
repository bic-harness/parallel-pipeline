export HARNESS_ACCOUNT_ID="${app.accountId}"
export HARNESS_APPLICATION_NAME="${app.name}"
export HARNESS_PIPELINE_NAME="${pipeline_name}"
export HARNESS_API_KEY="${api_key}"

# CSV to set list of environments to deploy to
export HARNESS_ENVIRONMENT_LIST="${environment_list}"

# CSV name:value (use to set infrastructure definition names)
export HARNESS_VARIABLE_INPUTS="${variable_inputs}"

# CSV serviceName:ArtifactSourceName:buildNumber
export HARNESS_SERVICE_INPUTS="${service_inputs}"

# Run Python script to launch and monitor pipelines to completion
python3 -u  << 'EOF'

import requests
import json
import os
import sys
import time
import datetime

ACCOUNT_ID = os.environ.get('HARNESS_ACCOUNT_ID')
API_KEY = os.environ.get('HARNESS_API_KEY')
APPLICATION_NAME = os.environ.get('HARNESS_APPLICATION_NAME')
PIPELINE_NAME = os.environ.get('HARNESS_PIPELINE_NAME')
SERVICE_INPUTS = os.environ.get('HARNESS_SERVICE_INPUTS')
VARIABLE_INPUTS = os.environ.get('HARNESS_VARIABLE_INPUTS')
ENVIRONMENT_LIST = os.environ.get('HARNESS_ENVIRONMENT_LIST') 

global URL
URL = "https://app.harness.io/gateway/api/graphql?accountId=" + ACCOUNT_ID

def getAppByName(appName):
    pload = '''
      { 
        applicationByName(name: "%s") { 
          id
        }
      } 
    ''' % (appName)

    #print ("Getting Harness App ID")

    response = requests.post(URL, headers={'x-api-key': API_KEY}, data=pload)
    json_response = response.json()
    appId = json_response['data']['applicationByName']['id']
    print ("Application: id=%s name=%s" % (appId, appName))

    return(appId)

def getPipelineByName(appId, plName):
    pload = '''
      {
        pipelineByName( pipelineName: "%s", applicationId: "%s") {
            id
        }
      }
    ''' % (plName, appId)

    #print ("Getting Harness Pipeline ID")

    response = requests.post(URL, headers={'x-api-key': API_KEY}, data=pload)
    json_response = response.json()
    plId = json_response['data']['pipelineByName']['id']
    print ("Pipeline: id=%s name=%s" % (plId, plName))

    return(plId)

def setServiceDetails(svcRef):
    pload = '''
      {
        service(serviceId: "%s"){
          name
          artifactSources{
            name
          }
        }
      }
    ''' % (svcRef['svc_id'])

    response = requests.post(URL, headers={'x-api-key': API_KEY}, data=pload)
    json_response = response.json()
    svcRef['svc_name'] = json_response['data']['service']['name']
    svcRef['artifact_name'] = json_response['data']['service']['artifactSources'][0]['name']
    print ("Service: svc_name=%s artifact_name=%s build_no=%s" % (svcRef['svc_name'], svcRef['artifact_name'], svcRef['build_no']))

def launchPipeline(appId, pipelineId, envRef, svcListRef, varListRef):

    # Build list of strings for serviceInputs
    svcStrList = []
    for svcRef in svcListRef:
      svcStrList.append('{ name: "%s", artifactValueInput: { valueType: BUILD_NUMBER buildNumber: { buildNumber: "%s" artifactSourceName: "%s" } } }' % (svcRef['svc_name'], svcRef['build_no'], svcRef['artifact_name']))

    # Build list of strings for variableInputs
    # Note: Initilise with target environment, where ${env} is pipline template variable name
    varStrList = [ '{ name: "env" variableValue: { type: NAME value: "%s" } }' % (envRef['env_name']) ]
    for varRef in varListRef:
      varStrList.append('{ name: "%s" variableValue: { type: NAME value: "%s" } }' % (varRef['name'], varRef['value']))
    
    # Set payload
    pload = '''
      mutation {
        startExecution(input: {
          applicationId: "%s"
          entityId: "%s"
          executionType: PIPELINE,
          variableInputs: [
            %s
          ]
          serviceInputs: [
            %s
          ]
        }
        ){
          clientMutationId
          execution{
            id
            status
          }
        }
      }
    ''' % (appId, pipelineId, "\n            ".join(varStrList), ",\n            ".join(svcStrList))

    print ("\n--- PIPELINE EXEC REQUEST ---")
    print (pload)

    response = requests.post(URL, headers={'x-api-key': API_KEY}, data=pload)
    json_response = response.json()

    print ("--- PIPELINE EXEC RESPONSE ---\n")
    print (json_response)

    envRef['exec_id'] = json_response['data']['startExecution']['execution']['id']
    envRef['exec_status'] = json_response['data']['startExecution']['execution']['status']

    # Initial status
    print ('%s: %s' % (envRef['env_name'], envRef['exec_status']))

def getExecStatus(execId):
    pload = '''
      { 
        execution(executionId: "%s") { 
          status
        }
      } 
    ''' % (execId)

    response = requests.post(URL, headers={'x-api-key': API_KEY}, data=pload)
    json_response = response.json()
    execStatus = json_response['data']['execution']['status']
    return(execStatus)

### Start of Main ###

DEFAULT='__default__'

# List of hashes to track status
envList=[]

# List of hashes for service inputs
svcList=[]

# List of hashes for variable inputs
varList=[]

app_id = getAppByName(APPLICATION_NAME)
pl_id = getPipelineByName(app_id, PIPELINE_NAME)

# Extract service inputs into list
for s in (SERVICE_INPUTS.split(',')):
  arr=s.split(':')
  svcList.append({'svc_id': arr[0], 'svc_name': DEFAULT, 'build_no': arr[1], 'artifact_name': DEFAULT})
  setServiceDetails(svcList[-1])

# Extract variable inputs into list
for v in (VARIABLE_INPUTS.split(',')):
  arr=v.split(':')
  varList.append({'name': arr[0], 'value': arr[1]})

# Launch pipelines (just take first service for now)
for env in (ENVIRONMENT_LIST.split(',')):
  envList.append({'env_name': env, 'exec_id': DEFAULT, 'exec_status': DEFAULT})
  launchPipeline(app_id, pl_id, envList[-1], svcList, varList)

# Number of pipelines launched
nTotal = len(envList)
IN_PROGRESS_STATES = ['RUNNING', 'PAUSED']

# Loop to completion
result={}
resstr={}
nDone = 0

print ("\n--- MONITORING PIPELINES TO COMPLETION ---\n")
while (1):
  for ref in (envList):
    curStatus = getExecStatus(ref['exec_id'])
    if curStatus != ref['exec_status']:

      # Updated status for this pipeline
      ref['exec_status'] = curStatus
      print ('%s: %s' % (ref['env_name'], ref['exec_status']))

      if curStatus not in IN_PROGRESS_STATES:
        # Job has finished
        if curStatus not in result.keys():
          # Initialise
          result[curStatus] = 0;
          resstr[curStatus] = [];

        # Increment count for this status
        result[curStatus] += 1
        resstr[curStatus].append(ref['env_name'])

        # Track number of finished pipelines
        nDone += 1

  if nDone == nTotal:
    print ("\n--- SUMMARY ---\n")
    print ("Total Pipelines: %s" % (nTotal))
    for key in result:
      resstr[key].sort
      print ('%s: %s (%s)' % (key, result[key], ','.join(resstr[key])))
    exit(0)

  time.sleep(10)

sys.exit(0)

EOF

exit $?