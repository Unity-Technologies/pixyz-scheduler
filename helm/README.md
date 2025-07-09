# How to use the pixyz scheduler helm

## Setup the infrastructure
Use your own tools for setup-ing your infrastructure:
 * kubernetes cluster
   * shared storage
   * redis

## Install the pixyz scheduler OCI helm
https://learn.microsoft.com/en-us/azure/container-registry/container-registry-helm-repos#authenticate-with-the-registry

```bash
USER_NAME="00000000-0000-0000-0000-000000000000"
ACR_NAME="unitypixyzinternal"
PASSWORD=$(az acr login --name $ACR_NAME --expose-token --output tsv --query accessToken)
helm registry login $ACR_NAME.azurecr.io \
  --username $USER_NAME \
  --password $PASSWORD
```

### For dev need to push to registry
helm\charts $ helm package pixyz-scheduler 
`helm push pixyz-scheduler-0.0.1.tgz oci://$ACR_NAME.azurecr.io/helm` 

### For user need to install in your registry
`helm install -n apps -f values.yaml scheduler oci://$ACR_NAME.azurecr.io/helm/pixyz-scheduler --version 0.0.1`
`helm upgrade -n apps -f values.yaml scheduler oci://$ACR_NAME.azurecr.io/helm/pixyz-scheduler --version 0.0.4`
# dev 
* in Chart.yaml directory: `helm template -n apps -f ../../../k8s/dev/values.yaml  .`
* direct output `helm template test helm`
* direct output with debug `helm template test helm --debug`
* with an output dir `helm template test helm --output-dir tmp` 
 

