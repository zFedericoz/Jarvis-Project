import { useState, useEffect, useRef } from "react";

interface Props {
  text: string;
  speed?: number;
}

export default function TypewriterText({ text, speed = 15 }: Props) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);
  const textRef = useRef(text);
  const posRef = useRef(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const prev = textRef.current;
    textRef.current = text;
    if (prev === "") {
      posRef.current = 0;
      setDisplayed("");
      setDone(false);
    } else if (text.startsWith(prev) && text.length > prev.length) {
      setDone(false);
    } else if (prev !== text) {
      posRef.current = 0;
      setDisplayed("");
      setDone(false);
    }
  }, [text]);

  useEffect(() => {
    if (done) return;

    intervalRef.current = setInterval(() => {
      const next = posRef.current + 1;
      if (next >= textRef.current.length) {
        setDisplayed(textRef.current);
        setDone(true);
        if (intervalRef.current) clearInterval(intervalRef.current);
      } else {
        posRef.current = next;
        setDisplayed(textRef.current.slice(0, next));
      }
    }, speed);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [speed, done]);

  return (
    <span>
      {displayed}
      {!done && <span style={{ animation: "blink 0.8s step-end infinite" }}>▋</span>}
    </span>
  );
}
