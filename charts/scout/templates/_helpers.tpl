{{/*
Common template helpers for naming and labels
*/}}

{{- define "scout.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "scout.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "scout.labels" -}}
app.kubernetes.io/name: {{ include "scout.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: Helm
{{- end -}}

{{- define "scout.selectorLabels" -}}
app.kubernetes.io/name: {{ include "scout.name" . }}
{{- end -}}

{{- define "scout.backend.fullname" -}}
{{ include "scout.fullname" . }}-backend
{{- end -}}

{{- define "scout.frontend.fullname" -}}
{{ include "scout.fullname" . }}-frontend
{{- end -}}

{{- define "scout.nginx.fullname" -}}
{{ include "scout.fullname" . }}-nginx
{{- end -}}


