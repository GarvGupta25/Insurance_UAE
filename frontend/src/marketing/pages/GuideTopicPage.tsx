import { useParams, Link } from 'react-router-dom';
import { PageShell, Section } from '../components';

export function GuideTopicPage() {
  const { topicSlug } = useParams();
  return (
    <PageShell>
      <Section>
        <h1>Guide: {topicSlug}</h1>
        <p>Guide topic detail — Phase 8.</p>
        <Link to="/guide" className="m-text-link">← Back to guide</Link>
      </Section>
    </PageShell>
  );
}
