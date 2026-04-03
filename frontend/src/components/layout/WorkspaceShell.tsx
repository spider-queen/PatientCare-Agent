import { PropsWithChildren, ReactNode } from "react";

type WorkspaceShellProps = PropsWithChildren<{
  left: ReactNode;
  right: ReactNode;
}>;

export function WorkspaceShell({ left, right, children }: WorkspaceShellProps) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,118,110,0.18),_transparent_32%),linear-gradient(135deg,_#f8fafc,_#eef6ff)] text-ink">
      <div className="mx-auto grid min-h-screen max-w-[1600px] gap-6 px-4 py-6 lg:grid-cols-[320px_minmax(0,1fr)_340px]">
        <aside className="space-y-4">{left}</aside>
        <main className="min-h-[calc(100vh-3rem)]">{children}</main>
        <aside className="space-y-4">{right}</aside>
      </div>
    </div>
  );
}

