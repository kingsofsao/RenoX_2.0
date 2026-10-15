import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { Button, EmptyState } from '../components/ui'

export function NotFoundPage() {
  return (
    <EmptyState icon={<Compass className="h-6 w-6" />} title="Page not found" description="That page does not exist."
      action={<Link to="/"><Button>Go to overview</Button></Link>} />
  )
}
