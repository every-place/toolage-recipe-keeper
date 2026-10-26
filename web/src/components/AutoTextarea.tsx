import { forwardRef, useEffect, useImperativeHandle, useRef, type TextareaHTMLAttributes } from "react";

// A textarea that grows with its text, so a long step never hides behind a scrollbar.
const AutoTextarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>((props, ref) => {
  const inner = useRef<HTMLTextAreaElement>(null);
  useImperativeHandle(ref, () => inner.current!);
  useEffect(() => {
    const el = inner.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight + 2}px`;
  }, [props.value]);
  return <textarea rows={1} {...props} ref={inner} style={{ minHeight: 48, resize: "none", overflow: "hidden", ...props.style }} />;
});

export default AutoTextarea;
