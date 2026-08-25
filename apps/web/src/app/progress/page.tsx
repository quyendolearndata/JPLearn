"use client";

import { useEffect, useState } from "react";
import type { LearnerProgress } from "@jplearn/domain";
import { api } from "../../lib/api";
import { getToken } from "../../lib/auth-storage";

export default function ProgressPage() {
  const [progress, setProgress] = useState<LearnerProgress | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    void api("/progress", { token })
      .then((res) => res.json())
      .then((body: LearnerProgress) => setProgress(body));
  }, []);

  return (
    <section>
      <h1>Tiến độ</h1>
      {progress ? (
        <p>
          {progress.minutes_comprehensible} phút · cấp {progress.current_ci_level}
        </p>
      ) : (
        <p>Hãy đăng nhập để xem phút CI.</p>
      )}
    </section>
  );
}
