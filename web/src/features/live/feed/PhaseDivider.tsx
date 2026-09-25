export function PhaseDivider({ children }: { children: string }) {
  return (
    <div className="flex items-center gap-3 text-12 tracking-[2px] whitespace-nowrap text-gold before:h-px before:flex-1 before:bg-gold-dark after:h-px after:flex-1 after:bg-gold-dark">
      {children}
    </div>
  );
}
