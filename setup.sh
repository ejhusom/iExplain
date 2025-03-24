#!/bin/bash
# Setup script for iExplain test infrastructure

# Create directory structure
mkdir -p iexplain/data/intents/natural_language
mkdir -p iexplain/data/logs/openstack
mkdir -p iexplain/data/metadata
mkdir -p iexplain/output
mkdir -p iexplain/templates

# Create the natural language intent file
cat > iexplain/data/intents/natural_language/nova_api_latency_intent.txt << 'EOL'
I need to improve the response time of our OpenStack Nova API service. Right now, users are experiencing delays when retrieving server details. I want to ensure that the API consistently responds in under 250 milliseconds, particularly for the GET requests to the servers/detail endpoint. Can you analyze our system and implement necessary changes to meet this performance target?
EOL

# Create the TMF intent file
cat > iexplain/data/intents/nova_api_latency_intent.ttl << 'EOL'
@prefix icm:  <http://tio.models.tmforum.org/tio/v3.6.0/IntentCommonModel/> .
@prefix dct:  <http://purl.org/dc/terms/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .
@prefix set:  <http://www.w3.org/2000/10/swap/set#> .
@prefix quan: <http://www.w3.org/2000/10/swap/quantities#> .
@prefix iexp: <http://intendproject.eu/iexplain#> .

iexp:I1 a icm:Intent ;
    dct:description "Improve API response time for OpenStack Nova service"@en ;
    log:allOf ( iexp:DE1 iexp:RE1 ) ;
.

iexp:DE1 a icm:DeliveryExpectation ;
    icm:target iexp:nova-api-service ;
    dct:description "Ensure Nova API response time is consistently under 250ms"@en ;
    log:allOf ( iexp:C1 iexp:CX1 ) ;
.

iexp:C1 a icm:Condition ;
    dct:description "API response time must be below threshold"@en ;
    set:forAll (
    _:X
    [ icm:valuesOfTargetProperty ( iexp:APIResponseTime ) ]
    quan:smaller ( _:X [ rdf:value "250"^^xsd:decimal ; quan:unit "ms" ] )
    ) ;
.

iexp:CX1 a icm:Context ;
    dct:description "Applied to Nova API GET /servers/detail endpoint"@en ;
    iexp:appliesToService "nova-api" ;
    iexp:appliesToEndpoint "/v2/servers/detail" ;
    iexp:httpMethod "GET" ;
.

iexp:RE1 a icm:ReportingExpectation ;
    icm:target iexp:monitoring-system ;
    dct:description "Report if Nova API response time expectation is met with metrics trends"@en ;
.
EOL

# Create second natural language intent file
cat > iexplain/data/intents/natural_language/vm_startup_time_intent.txt << 'EOL'
My team has been noticing that virtual machine startup times are taking too long. We need to reduce the time it takes to provision a new VM instance to under 30 seconds. This is causing delays in our continuous integration pipeline. Please focus on optimizing the VM creation process in our OpenStack environment.
EOL

# Create second TMF intent file
cat > iexplain/data/intents/vm_startup_time_intent.ttl << 'EOL'
@prefix icm:  <http://tio.models.tmforum.org/tio/v3.6.0/IntentCommonModel/> .
@prefix dct:  <http://purl.org/dc/terms/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .
@prefix set:  <http://www.w3.org/2000/10/swap/set#> .
@prefix quan: <http://www.w3.org/2000/10/swap/quantities#> .
@prefix iexp: <http://intendproject.eu/iexplain#> .

iexp:I2 a icm:Intent ;
    dct:description "Reduce VM instance startup time in OpenStack Nova"@en ;
    log:allOf ( iexp:DE2 iexp:RE2 ) ;
.

iexp:DE2 a icm:DeliveryExpectation ;
    icm:target iexp:nova-compute-service ;
    dct:description "Ensure VM instance provisioning takes less than 30 seconds"@en ;
    log:allOf ( iexp:C2 iexp:CX2 ) ;
.

iexp:C2 a icm:Condition ;
    dct:description "VM startup time must be below threshold"@en ;
    set:forAll (
    _:X
    [ icm:valuesOfTargetProperty ( iexp:VMStartupTime ) ]
    quan:smaller ( _:X [ rdf:value "30"^^xsd:decimal ; quan:unit "s" ] )
    ) ;
.

iexp:CX2 a icm:Context ;
    dct:description "Applied to all VM instance types"@en ;
    iexp:appliesToService "nova-compute" ;
    iexp:instanceFlavor "all" ;
.

iexp:RE2 a icm:ReportingExpectation ;
    icm:target iexp:monitoring-system ;
    dct:description "Report if VM startup time expectation is met with metrics trends"@en ;
.
EOL

# Create the mapping file
cat > iexplain/data/intents/intent_mapping.json << 'EOL'
{
  "nova_api_latency_intent.ttl": {
    "natural_language_file": "natural_language/nova_api_latency_intent.txt",
    "description": "Improve Nova API response time",
    "created_date": "2023-05-01",
    "id": "I1"
  },
  "vm_startup_time_intent.ttl": {
    "natural_language_file": "natural_language/vm_startup_time_intent.txt",
    "description": "Reduce VM instance startup time",
    "created_date": "2023-05-02",
    "id": "I2"
  }
}
EOL

# Create sample log files
cat > iexplain/data/logs/openstack/nova-api.log << 'EOL'
2017-05-16 00:00:00.008 25746 INFO nova.osapi_compute.wsgi.server [req-38101a0b-2096-447d-96ea-a692162415ae 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2477829
2017-05-16 00:00:00.272 25746 INFO nova.osapi_compute.wsgi.server [req-9bc36dd9-91c5-4314-898a-47625eb93b09 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2577181
2017-05-16 00:00:01.551 25746 INFO nova.osapi_compute.wsgi.server [req-55db2d8d-cdb7-4b4b-993b-429be84c0c3e 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2731631
2017-05-16 00:00:01.813 25746 INFO nova.osapi_compute.wsgi.server [req-2a3dc421-6604-42a7-9390-a18dc824d5d6 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2580249
2017-05-16 00:00:03.091 25746 INFO nova.osapi_compute.wsgi.server [req-939eb332-c1c1-4e67-99b8-8695f8f1980a 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2727931
2017-05-16 00:00:03.358 25746 INFO nova.osapi_compute.wsgi.server [req-b6a4fa91-7414-432a-b725-52b5613d3ca3 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2642131
2017-05-16 00:00:04.789 25746 INFO nova.osapi_compute.wsgi.server [req-bbfc3fb8-7cb3-4ac8-801e-c893d1082762 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.4256971
2017-05-16 00:00:05.060 25746 INFO nova.osapi_compute.wsgi.server [req-31826992-8435-4e03-bc09-ba9cca2d8ef9 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2661140
2017-05-16 00:00:06.321 25746 INFO nova.osapi_compute.wsgi.server [req-7160b3e7-676b-498f-b147-7759d8eaea76 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2563808
2017-05-16 00:00:06.584 25746 INFO nova.osapi_compute.wsgi.server [req-e46f1fc1-61ce-4673-b3c7-f8bd94554273 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2580891
2017-05-16 00:00:07.864 25746 INFO nova.osapi_compute.wsgi.server [req-546e2e6a-b85e-434a-91dc-53a0a9124a4f 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2733629
2017-05-16 00:00:08.137 25746 INFO nova.osapi_compute.wsgi.server [req-e2c35e53-06d3-4feb-84b9-705c94d40e5b 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2694771
2017-05-16 00:00:09.411 25746 INFO nova.osapi_compute.wsgi.server [req-ce9c8a59-c9ba-43b1-9735-318ceabc9216 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2692339
2017-05-16 00:00:09.692 25746 INFO nova.osapi_compute.wsgi.server [req-e1da47c6-0f46-4ce8-940c-05397a5fab9e 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2777061
2017-05-16 00:00:12.782 25746 INFO nova.osapi_compute.wsgi.server [req-9dac2436-7927-4e4d-9db0-fe35a2bf6ce3 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.5215032
2017-05-16 00:00:13.954 25746 INFO nova.osapi_compute.wsgi.server [req-f456fc92-3d52-4371-b6ce-70e1925cbe54 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.3821654
2017-05-16 00:00:14.227 25746 INFO nova.osapi_compute.wsgi.server [req-7c98c92e-959e-4cac-89d3-1a9b5683be39 113d3a99c3da401fbd62cc2caa5b96d2 54fadb412c4e40cdbaed9335e4c35a9e - - -] 10.11.10.1 "GET /v2/54fadb412c4e40cdbaed9335e4c35a9e/servers/detail HTTP/1.1" status: 200 len: 1893 time: 0.2691371
EOL

cat > iexplain/data/logs/openstack/nova-compute.log << 'EOL'
2017-05-16 00:00:04.500 2931 INFO nova.compute.manager [req-3ea4052c-895d-4b64-9e2d-04d64c4d94ab - - - - -] [instance: b9000564-fe1a-409b-b8cc-1e88b294cd1d] VM Started (Lifecycle Event)
2017-05-16 00:00:36.562 2931 INFO nova.compute.manager [req-3ea4052c-895d-4b64-9e2d-04d64c4d94ab - - - - -] [instance: b9000564-fe1a-409b-b8cc-1e88b294cd1d] Instance spawned in 32.06 seconds
2017-05-16 00:01:05.185 2931 INFO nova.virt.libvirt.imagecache [req-addc1839-2ed5-4778-b57e-5854eb7b8b09 - - - - -] image 0673dd71-34c5-4fbb-86c4-40623fbe45b4 at (/var/lib/nova/instances/_base/a489c868f0c37da93b76227c91bb03908ac0e742): checking
2017-05-16 00:02:01.500 2931 INFO nova.compute.manager [req-5ff2a5e1-895d-4b64-9e2d-04d64c4d91aa - - - - -] [instance: c8100abc-fe1a-409b-b8cc-1e88b294efab] VM Started (Lifecycle Event)
2017-05-16 00:02:35.123 2931 INFO nova.compute.manager [req-5ff2a5e1-895d-4b64-9e2d-04d64c4d91aa - - - - -] [instance: c8100abc-fe1a-409b-b8cc-1e88b294efab] Instance spawned in 33.62 seconds
2017-05-16 00:03:22.500 2931 INFO nova.compute.manager [req-7de12fc9-795d-4b64-9e2d-04d64c4d92bb - - - - -] [instance: d7200fed-fe1a-409b-b8cc-1e88b294ffcd] VM Started (Lifecycle Event)
2017-05-16 00:03:54.760 2931 INFO nova.compute.manager [req-7de12fc9-795d-4b64-9e2d-04d64c4d92bb - - - - -] [instance: d7200fed-fe1a-409b-b8cc-1e88b294ffcd] Instance spawned in 32.26 seconds
EOL

echo "Sample data files created!"