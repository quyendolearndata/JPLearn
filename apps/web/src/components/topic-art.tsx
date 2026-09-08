/** Decorative topic art; not a video thumbnail. */
export function TopicArt({ topic = "culture" }: { topic?: string }) {
  const food = topic === "food";
  return <svg viewBox="0 0 440 280" aria-hidden="true" focusable="false">
    <rect width="440" height="280" fill={food ? "#e7c3a8" : topic === "daily_home" ? "#e9ddc5" : "#dce5d0"}/>
    {topic === "nature" ? <><circle cx="310" cy="70" r="30" fill="#f0d4a5"/><path d="M0 215Q110 55 225 210Q330 90 440 180V280H0" fill="#8ba28a"/><path d="M0 250Q145 155 290 245Q365 195 440 220V280H0" fill="#59775b"/></> : food ? <><ellipse cx="220" cy="165" rx="130" ry="75" fill="#faf5e7"/><path d="M140 188l42-72q12-20 24 0l42 72zm93 0 34-62q10-20 22 0l34 62z" fill="#fffdf0"/><path d="M181 171h31v29h-31zm83 0h30v29h-30z" fill="#425d47"/><path d="M100 65l230 4m-225 14 230 4" stroke="#966446" strokeWidth="7" strokeLinecap="round"/></> : <><ellipse cx="215" cy="225" rx="130" ry="17" fill="#b7ba99"/><path d="M108 142h155l-20 75H131z" fill="#fff9e9"/><path d="M262 151c68-12 66 63-12 48" stroke="#fff9e9" strokeWidth="14" fill="none"/><ellipse cx="186" cy="142" rx="78" ry="16" fill="#6f8861"/><path d="M162 112c-26-25 25-29 0-58m41 60c-22-21 20-28 0-51" stroke="#fff9e9" strokeWidth="6" fill="none" strokeLinecap="round"/><path d="M309 226V76m0 54q-54-42-28-68 39 13 28 68m0 37q54-42 61-13-18 35-61 13" stroke="#71865c" fill="#71865c" strokeWidth="5"/></>}
  </svg>;
}
