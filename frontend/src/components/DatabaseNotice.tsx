import { useHealth } from '../hooks/HealthContext'
import { Alert, Button } from './ui'

/** Explains why data is missing when the API or FalkorDB is not usable. Renders nothing when healthy. */
export function DatabaseNotice() {
  const { health, error, refresh } = useHealth()
  const retry = <Button variant="secondary" onClick={refresh}>Retry</Button>

  if (error) {
    return (
      <Alert tone="error" title="Backend unreachable" action={retry}>
        {error.message} Start it with <code className="rounded bg-red-100 px-1">uvicorn app.main:app --port 8000</code> from the backend folder.
      </Alert>
    )
  }
  if (!health) return null
  if (health.database.status === 'not_configured') {
    return (
      <Alert tone="warning" title="FalkorDB is not configured" action={retry}>
        Set <code className="rounded bg-amber-100 px-1">FALKORDB_URL</code> in <code className="rounded bg-amber-100 px-1">backend/.env</code> and restart the backend. Papers cannot be stored until then.
      </Alert>
    )
  }
  if (health.database.status === 'unavailable') {
    return (
      <Alert tone="error" title="FalkorDB is unavailable" action={retry}>
        The API is running but cannot reach the graph database ({health.database.message ?? 'connection failed'}). Check that your FalkorDB Cloud instance is running.
      </Alert>
    )
  }
  return null
}
