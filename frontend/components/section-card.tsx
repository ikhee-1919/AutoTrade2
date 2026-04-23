import { ReactNode } from "react";

type SectionCardProps = {
  title: string;
  description?: string;
  children: ReactNode;
};

export function SectionCard({ title, description, children }: SectionCardProps) {
  return (
    <section className="card">
      <h2>{title}</h2>
      {description ? <p className="small">{description}</p> : null}
      {children}
    </section>
  );
}
