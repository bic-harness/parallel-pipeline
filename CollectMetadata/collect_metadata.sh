# Service Variables 
export serviceName=${service.name}

# Infra Variables
export infraName=${infra.name}

# Artifact Variables
export buildNo=${artifact.buildNo}

# We only expect one service id in ${artifact.serviceIds}
# Example format: [qJ9MbG6hTRSacrnQy20Duw]
# Need to remove the square brackets
export serviceId=`echo ${artifact.serviceIds} | awk '{ gsub(/\[/,""); gsub(/]/, ""); print $1 }'`

# Set up service inputs format (for use in runParallelPipelines stage)
export inputs="${serviceId}:${buildNo}"