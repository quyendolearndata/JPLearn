"use client";

import { useEffect, useMemo, useState } from "react";
import type { CatalogItemPublic } from "@jplearn/domain";
import { api } from "../lib/api";
import { getToken } from "../lib/auth-storage";

export default function HomePage() {
  const [items, setItems] = useState<CatalogItemPublic[]>([]);
  const [message, setMessage] = useState("Đang tải…");

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setMessage("Hãy đăng nhập.");
      return;
    }
    void api("/catalog", { token })
      .then((res) => res.json())
      .then((body: { items: CatalogItemPublic[] }) => {
        setItems(body.items ?? []);
        setMessage("");
      });
  }, []);

  const grouped = useMemo(() => {
    const map = new Map<number, CatalogItemPublic[]>();
    for (const item of items) {
      const list = map.get(item.ci_level) ?? [];
      list.push(item);
      map.set(item.ci_level, list);
    }
    return [...map.entries()].sort((a, b) => a[0] - b[0]);
  }, [items]);

  return (
    <section>
      <h1>Catalog</h1>
      {message ? <p>{message}</p> : null}
      {grouped.map(([level, list]) => (
        <div key={level}>
          <h2>Cấp {level}</h2>
          <ul>
            {list.map((item) => (
              <li key={item.id}>
                {item.topic_id} · {item.media_type} · {item.duration_seconds}s
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
