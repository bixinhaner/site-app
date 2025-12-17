import request from '@/utils/request'

export const siteSurveyStageApi = {
  downloadTemplate: (action = 'skip') =>
    request.get('/api/sites/survey-stage/batch-template', { params: { action }, responseType: 'blob' }),

  batchUpload: (file, action = 'skip', dryRun = true) => {
    const form = new FormData()
    form.append('file', file)
    const url = `/api/sites/survey-stage/batch-upload?action=${encodeURIComponent(action)}&dry_run=${dryRun}`
    return request.post(url, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  }
}

export default siteSurveyStageApi

