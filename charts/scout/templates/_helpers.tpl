{{/*
Expand the name of the chart.
*/}}
{{- define "scout.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "scout.fullname" -}}
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
{{- define "scout.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "scout.labels" -}}
helm.sh/chart: {{ include "scout.chart" . }}
{{ include "scout.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "scout.selectorLabels" -}}
app.kubernetes.io/name: {{ include "scout.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "scout.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "scout.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Image name helper
*/}}
{{- define "scout.image" -}}
{{- $registry := .Values.global.imageRegistry | default .Values.global.defaultImageRegistry -}}
{{- $repository := .repository -}}
{{- $tag := .tag | default "latest" -}}
{{- if and $registry (ne $registry "") -}}
{{- printf "%s/%s:%s" $registry $repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}
{{- end -}}

{{/*
Namespace name
*/}}
{{- define "scout.namespace" -}}
{{- if .Values.namespace.create -}}
{{- .Values.namespace.name -}}
{{- else -}}
{{- .Values.namespace.name -}}
{{- end -}}
{{- end -}}

{{/*
Redis host name
*/}}
{{- define "scout.redis.host" -}}
{{- printf "%s-redis" (include "scout.fullname" .) -}}
{{- end -}}

{{/*
Backend service name
*/}}
{{- define "scout.backend.serviceName" -}}
{{- printf "%s-backend" (include "scout.fullname" .) -}}
{{- end -}}

{{/*
Frontend service name
*/}}
{{- define "scout.frontend.serviceName" -}}
{{- printf "%s-frontend" (include "scout.fullname" .) -}}
{{- end -}}

{{/*
Nginx service name
*/}}
{{- define "scout.nginx.serviceName" -}}
{{- printf "%s-nginx" (include "scout.fullname" .) -}}
{{- end -}}

{{/*
Prometheus service name
*/}}
{{- define "scout.prometheus.serviceName" -}}
{{- printf "%s-prometheus" (include "scout.fullname" .) -}}
{{- end -}}

{{/*
Redis service name
*/}}
{{- define "scout.redis.serviceName" -}}
{{- printf "%s-redis" (include "scout.fullname" .) -}}
{{- end -}} 