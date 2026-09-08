import Link from "next/link";

export function PageHeading({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="workspace-heading">
      <div>
        {eyebrow ? <p className="workspace-eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {description ? <p className="workspace-description">{description}</p> : null}
      </div>
      {actions ? <div className="workspace-actions">{actions}</div> : null}
    </header>
  );
}

export function AccessState({
  staff = false,
  title,
  message,
}: {
  staff?: boolean;
  title?: string;
  message?: string;
}) {
  return (
    <section className="workspace-empty" aria-live="polite">
      <h1>{title ?? (staff ? "Không có quyền truy cập" : "Hãy đăng nhập để tiếp tục")}</h1>
      <p>
        {message ?? (staff
          ? "Khu vực này dành cho tài khoản giáo viên hoặc quản trị viên."
          : "Tài khoản giúp đồng bộ tiến độ và thư viện trên các thiết bị.")}
      </p>
      <Link className="btn-cta btn-primary" href="/login">Đến trang tài khoản</Link>
    </section>
  );
}

export function LoadingState({ label = "Đang tải dữ liệu…" }: { label?: string }) {
  return <div className="workspace-loading" role="status">{label}</div>;
}

export function EmptyState({ title, body, description }: { title: string; body?: string; description?: string }) {
  return (
    <div className="workspace-empty">
      <h2>{title}</h2>
      <p>{body ?? description}</p>
    </div>
  );
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="status-error" role="alert">
      <p>{message}</p>
      {retry ? <button type="button" onClick={retry}>Thử lại</button> : null}
    </div>
  );
}
