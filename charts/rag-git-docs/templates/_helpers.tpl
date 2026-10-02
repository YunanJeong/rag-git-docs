{{/* 리소스 이름. 릴리스 이름에 차트 이름이 들어 있으면 한 번만 쓴다 */}}
{{- define "rag.name" -}}
{{- .Values.nameOverride | default .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "rag.fullname" -}}
{{- $name := include "rag.name" . -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "rag.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
app.kubernetes.io/name: {{ include "rag.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/* selector 는 한 번 만들면 바꿀 수 없으므로 버전처럼 바뀌는 값은 넣지 않는다 */}}
{{- define "rag.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rag.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "rag.image" -}}
{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}
{{- end -}}

{{/* 검색 서버와 수집·색인이 함께 쓰는 Qdrant 접속 정보 */}}
{{- define "rag.qdrantEnv" -}}
- name: QDRANT_URL
  value: {{ .Values.qdrant.url | quote }}
{{- with .Values.qdrant.apiKeySecret.name }}
- name: QDRANT_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ . }}
      key: {{ $.Values.qdrant.apiKeySecret.key }}
{{- end }}
{{- end -}}

{{/* 토큰 Secret. existingSecret 을 주면 차트가 만들지 않고 그걸 쓴다 */}}
{{- define "rag.secretName" -}}
{{- .Values.existingSecret | default (printf "%s-env" (include "rag.fullname" .)) -}}
{{- end -}}
