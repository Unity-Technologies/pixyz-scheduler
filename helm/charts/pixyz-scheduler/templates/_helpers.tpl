{{/*
Expand the name of the chart.
*/}}
{{- define "helm.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "helm.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "helm.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "helm.labels" -}}
helm.sh/chart: {{ include "helm.chart" . }}
{{ include "helm.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "helm.selectorLabels" -}}
app.kubernetes.io/name: {{ include "helm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "helm.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "helm.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Define a custom template function to convert size to bytes
*/}}
{{- define "utils.sizeToKBytes" -}}
{{- $length := int (sub (len .) 2) -}}       {{/* Get the length of the string excluding the last two characters */}}
{{- $value := substr 0 $length . -}}         {{/* Extract the size value */}}
{{- $unit := substr $length (len .) . -}}    {{/* Extract the unit */}}

{{- if eq $unit "Gi" -}}                     {{/* Check if the unit is Gi */}}
  {{- mul $value 1048576 -}}              {{/* Convert Gi to bytes (1Gi = 1073741824 bytes) */}}
{{- else if eq $unit "Mi" -}}                {{/* Check if the unit is Mi */}}
  {{- mul $value 1024 -}}                 {{/* Convert Mi to bytes (1Mi = 1048576 bytes) */}}
{{- else if eq $unit "Ki" -}}                {{/* Check if the unit is Ki */}}
  {{- mul $value 1 -}}                    {{/* Convert Ki to bytes (1Ki = 1024 bytes) */}}
{{- else -}}
  {{- printf "Unsupported unit: %s" $unit }} {{/* Handle unsupported units */}}
{{- end -}}
{{- end -}}