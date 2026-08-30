/**
 * RecommendationCard - OWNER: Member 1, CONSUMED BY Member 2's dashboard.
 * Keep these props stable after week 2. See plan.md 6.5.
 *
 * Every recommendation carries a human-readable reason - never render one without it.
 */
import { Card, Badge, Button } from '../ui';

export default function RecommendationCard({ kind, title, reason, onOpen, onDismiss }) {
  return (
    <Card className="flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <h4 className="font-medium">{title}</h4>
        <Badge tone="primary">{kind}</Badge>
      </div>
      <p className="text-sm text-slate-500">{reason}</p>
      <div className="mt-2 flex gap-2">
        <Button size="sm" onClick={onOpen}>
          Start
        </Button>
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          Not now
        </Button>
      </div>
    </Card>
  );
}
