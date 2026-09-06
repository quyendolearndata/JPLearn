"use client";

import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="landing-wrapper">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-grid">
          <div className="hero-content">
            <div className="vertical-badges">
              <span className="v-badge">耳から染み込む</span>
              <span className="v-badge">日本語を</span>
              <span className="v-badge">自然に習得</span>
            </div>

            <h1 className="hero-title">
              Hấp thu tiếng Nhật tự nhiên bằng phương pháp Comprehensible Input.
            </h1>

            <p className="hero-lead">
              Ghi nhớ quy tắc máy móc chỉ khiến phản xạ của bạn chậm chạp. Phương pháp Comprehensible Input (CI) của JPLearn giúp bạn hấp thu ngôn ngữ như tiếng mẹ đẻ qua các video trực quan phân cấp khoa học.
            </p>

            <div className="hero-cta-group">
              <Link href="/login" className="btn-cta btn-primary" style={{ padding: "0.85rem 1.8rem", fontSize: "1.05rem" }}>
                Bắt đầu học ngay
              </Link>
              <Link href="/catalog" className="btn-cta btn-secondary" style={{ padding: "0.85rem 1.8rem", fontSize: "1.05rem" }}>
                Khám phá Catalog
              </Link>
            </div>
          </div>

          {/* Organic Blob Video Mask Demo */}
          <div className="hero-visual">
            <div className="blob-card">
              <div className="blob-screen">
                <div className="blob-tag">CẤP ĐỘ 0 · TRỰC QUAN CAO</div>
                <div className="blob-center-icon">
                  <span style={{ fontSize: "2rem", display: "inline-block", transform: "translateY(-1px)" }}>▶</span>
                </div>
                <div className="blob-caption">
                  <div style={{ fontWeight: 800, fontSize: "1.1rem" }}>「何を食べますか」</div>
                  <div style={{ fontSize: "0.8rem", color: "#a8a29e", marginTop: "4px" }}>
                    Nghe hiểu qua cử chỉ & hình ảnh minh họa
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Wavy Ribbon Banner */}
      <section className="ribbon-banner">
        <div className="ribbon-inner">
          <span className="ribbon-text">100% NẠP TIẾNG NHẬT TỰ NHIÊN TRỰC QUAN</span>
          <Link href="/catalog" className="btn-cta btn-secondary" style={{ color: "var(--charcoal)" }}>
            Xem toàn bộ bài học
          </Link>
        </div>
      </section>

      {/* 3 Core Strengths (Bento Grid) */}
      <section className="strengths-section">
        <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
          <span style={{ color: "#9f1239", fontWeight: 900, fontSize: "0.85rem", letterSpacing: "1.5px", textTransform: "uppercase" }}>
            3 Giá Trị Cốt Lõi
          </span>
          <h2 style={{ fontSize: "2.2rem", marginTop: "0.5rem" }}>Tại sao nên học cùng JPLearn?</h2>
          <p style={{ color: "var(--text-muted)" }}>Học ngôn ngữ tự nhiên không cần tra từ điển liên tục</p>
        </div>

        <div className="strengths-grid">
          <div className="strength-card">
            <span className="strength-point">POINT 01</span>
            <h3>100% Tư Duy Trực Tiếp</h3>
            <p style={{ color: "var(--text-muted)", fontSize: "0.95rem", lineHeight: 1.7 }}>
              Loại bỏ hoàn toàn thói quen dịch thầm trong đầu. Hình ảnh động và cử chỉ tay sinh động giúp não bộ kết nối trực tiếp khái niệm với âm thanh tiếng Nhật.
            </p>
          </div>

          <div className="strength-card">
            <span className="strength-point">POINT 02</span>
            <h3>Phân Cấp Chuẩn i+1</h3>
            <p style={{ color: "var(--text-muted)", fontSize: "0.95rem", lineHeight: 1.7 }}>
              Các video được thiết kế theo cấp độ từ 0 đến 4, giúp bạn luôn hiểu 85–90% ngữ cảnh. Lượng từ vựng và cấu trúc mới được tiếp thu dễ dàng mà không gây quá tải.
            </p>
          </div>

          <div className="strength-card">
            <span className="strength-point">POINT 03</span>
            <h3>Đo Lường Phút CI Thực Tế</h3>
            <p style={{ color: "var(--text-muted)", fontSize: "0.95rem", lineHeight: 1.7 }}>
              Từng phút bạn tập trung xem video trong phiên học được server xác nhận và tích lũy vào chỉ số Comprehensible Minutes, chứng minh sự tiến bộ mỗi ngày.
            </p>
          </div>
        </div>
      </section>

      {/* Comparison Table */}
      <section className="comparison-section">
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <span style={{ color: "#0369a1", fontWeight: 900, fontSize: "0.85rem", letterSpacing: "1.5px", textTransform: "uppercase" }}>
            So Sánh Phương Pháp
          </span>
          <h2 style={{ fontSize: "2rem", marginTop: "0.5rem" }}>Học Vẹt Truyền Thống vs JPLearn CI</h2>
        </div>

        <div className="comparison-table-wrapper">
          <table className="comparison-table">
            <thead>
              <tr>
                <th style={{ width: "34%" }}>Tiêu chí</th>
                <th style={{ width: "33%" }}>Phương pháp cũ</th>
                <th style={{ width: "33%", background: "#fff1f2", color: "#9f1239" }}>★ JPLearn (CI Method)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ fontWeight: 700 }}>Tốc độ phản xạ giao tiếp</td>
                <td style={{ color: "var(--text-muted)" }}>✕ Chậm (Phải dịch qua lại trong đầu)</td>
                <td style={{ background: "#fff1f2", fontWeight: 700 }}>◎ Tức thì (Tư duy trực tiếp bằng tiếng Nhật)</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700 }}>Trải nghiệm học tập</td>
                <td style={{ color: "var(--text-muted)" }}>✕ Căng thẳng (Học thuộc lòng khô khan)</td>
                <td style={{ background: "#fff1f2", fontWeight: 700 }}>◎ Thoải mái (Xem video kết nối ngữ cảnh)</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700 }}>Ngữ điệu & Giọng nói</td>
                <td style={{ color: "var(--text-muted)" }}>△ Cứng nhắc (Ít nghe ngữ cảnh hội thoại)</td>
                <td style={{ background: "#fff1f2", fontWeight: 700 }}>◎ Chuẩn bản xứ tự nhiên qua clip</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700 }}>Ghi nhận tiến độ</td>
                <td style={{ color: "var(--text-muted)" }}>✕ Điểm số lý thuyết</td>
                <td style={{ background: "#fff1f2", fontWeight: 700 }}>◎ Tích lũy phút CI thực tế được xác nhận</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div style={{ textAlign: "center", marginTop: "3rem" }}>
          <Link href="/login" className="btn-cta btn-primary" style={{ padding: "1rem 2.5rem", fontSize: "1.1rem" }}>
            Đăng ký trải nghiệm ngay
          </Link>
        </div>
      </section>
    </div>
  );
}
