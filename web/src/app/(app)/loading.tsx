/** Shown inside the frame while a page fetches, so moving between pages never blanks the screen. */
export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <div className="skeleton h-9 w-56" />
      <div className="skeleton mt-3 h-5 w-96 max-w-full" />
      <div className="mt-8 space-y-3">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="skeleton h-[72px] rounded-2xl" style={{ opacity: 1 - i * 0.12 }} />
        ))}
      </div>
    </div>
  );
}
