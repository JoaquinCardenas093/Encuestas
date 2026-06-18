interface ResultSummary {
  patterns_valid: number
  patterns_dropped: number
  patterns_repaired: number
  estimated_cost_usd?: number
}

interface AnalysisJobState {
  jobId: string
  progress: number
  status: "running" | "done" | "error"
  message: string
  resultSummary?: ResultSummary
  error?: string
}

interface Props {
  job: AnalysisJobState
  onClose(): void
}

export default function AnalysisProgressModal({ job: _job, onClose: _onClose }: Props) {
  return <div>AnalysisProgressModal placeholder</div>
}
