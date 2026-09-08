import Link from "next/link";
import { TopicArt } from "../components/topic-art";

export default function LandingPage() {
  return <div>
    <section className="ab-hero">
      <div className="ab-hero-copy"><p className="eyebrow">Nghe · Quan sát · Thấu hiểu</p>
        <h1>Một chút tiếng Nhật.<br/>Một điều mới mỗi ngày.</h1>
        <p>Bắt đầu từ những câu chuyện gần gũi. Chọn một video vừa sức và cùng khám phá.</p>
        <div className="button-group"><Link href="/catalog" className="btn-cta btn-primary">Khám phá Catalog ↗</Link><Link href="/login" className="btn-cta btn-secondary">Bắt đầu học ngay</Link></div>
      </div><div className="ab-hero-art"><TopicArt /></div>
    </section>
    <h2>Tiếng Nhật, theo nhịp của bạn.</h2><p className="muted">Lắng nghe và quan sát trong những tình huống đời thường.</p>
    <div className="strengths-grid">
      {[['01','Chọn điều bạn tò mò','Khám phá nội dung theo chủ đề và cấp độ CI từ 0 đến 4.'],['02','Hiểu qua ngữ cảnh','Hình ảnh và cử chỉ giúp bạn theo dõi câu chuyện bằng tiếng Nhật.'],['03','Từng bước mỗi ngày','Kết thúc phiên để ghi nhận thời gian học và xem tiến độ của bạn.']].map(([n,title,body])=><article className="strength-card" key={n}><p className="eyebrow">{n}</p><h3>{title}</h3><p className="muted">{body}</p></article>)}
    </div>
    <div className="ab-note"><span aria-hidden="true">❧</span><div><h2>Một video nữa, khi bạn sẵn sàng.</h2><p>Không cần vội. Hãy bắt đầu từ điều khiến bạn tò mò.</p></div><Link href="/catalog" className="btn-cta">Xem toàn bộ bài học</Link></div>
  </div>;
}
