/** A new page eases in; the frame around it does not move. */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="fade-up">{children}</div>;
}
