import type { Item } from "@genux/shared";

/** Static UX: a component written in advance. The agent only chooses it and supplies an `Item`. */
export function ItemCard({ item, onSelect }: { item: Item; onSelect?: (id: string) => void }) {
  return (
    <article className="card item-card" data-component="ItemCard">
      <header className="row-between">
        <h3 className="card-title">{item.name}</h3>
        <span className="badge tone-info">{item.category}</span>
      </header>
      <p className="muted">{item.summary}</p>
      <div className="stack row gap-m">
        <div className="metric"><div className="metric-label">Price</div><div className="metric-value">${item.price}</div></div>
        <div className="metric tone-success"><div className="metric-label">Rating</div><div className="metric-value">{item.rating}</div></div>
        <div className="metric"><div className="metric-label">Battery</div><div className="metric-value">{item.batteryHours} h</div></div>
      </div>
      {onSelect && <button type="button" className="btn secondary" onClick={() => onSelect(item.id)}>Select</button>}
    </article>
  );
}
