"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const TOUR_KEY = "hgr-tour-seen-v1";

type TourStep = {
  selector: string;
  title: string;
  body: string;
  /** Preferred card placement relative to the target. */
  placement: "bottom" | "top" | "right" | "left";
};

const STEPS: TourStep[] = [
  {
    selector: ".shell-brand",
    title: "Welcome to Mission Control",
    body: "This is the HolyGrail enterprise operator console. You can manage AI missions, monitor agents, and observe every phase of the Smelt-Cycle from here.",
    placement: "right",
  },
  {
    selector: ".shell-nav",
    title: "Navigate the System",
    body: "Browse all operational pages from the sidebar — Workflow pages for launching missions, Observability for monitoring, and Configuration for settings.",
    placement: "right",
  },
  {
    selector: ".cmd-palette-trigger",
    title: "Search Anything (Ctrl+K)",
    body: "Click here or press Ctrl+K to open the command palette. Jump to any page, search missions, agents, and logic nodes — all from your keyboard.",
    placement: "bottom",
  },
  {
    selector: ".shell-header-actions .primary-button",
    title: "Launch a New Mission",
    body: "Start a new mission by chatting with the PM Agent. Describe what you want to build and the Smelt-Cycle will take it from there.",
    placement: "bottom",
  },
  {
    selector: ".notif-bell-wrap",
    title: "Stay on Top of Alerts",
    body: "The notification bell shows open system alerts in real time. Critical alerts also trigger an OS notification when you're in another tab.",
    placement: "bottom",
  },
];

type Rect = { top: number; left: number; right: number; bottom: number; width: number; height: number };

const CARD_W = 300;
const CARD_H_APPROX = 200; // rough height for placement calculations
const MARGIN = 16;

function computeCardPosition(
  targetRect: Rect,
  placement: TourStep["placement"],
): { top: number; left: number } {
  const vw = window.innerWidth;
  const vh = window.innerHeight;

  let top = 0;
  let left = 0;

  switch (placement) {
    case "right":
      top = targetRect.top;
      left = targetRect.right + MARGIN;
      break;
    case "left":
      top = targetRect.top;
      left = targetRect.left - CARD_W - MARGIN;
      break;
    case "bottom":
      top = targetRect.bottom + MARGIN;
      left = targetRect.left;
      break;
    case "top":
    default:
      top = targetRect.top - CARD_H_APPROX - MARGIN;
      left = targetRect.left;
      break;
  }

  // Clamp to viewport with margin.
  left = Math.max(MARGIN, Math.min(left, vw - CARD_W - MARGIN));
  top = Math.max(MARGIN, Math.min(top, vh - CARD_H_APPROX - MARGIN));

  return { top, left };
}

/**
 * 6B — First-visit guided tour.
 *
 * Shown automatically on first load (localStorage key missing) or by dispatching
 * the custom event "guided-tour-open". A semi-transparent spotlight highlights the
 * target element. The card floats alongside it.
 *
 * 6 steps covering: sidebar, navigation, command palette, new mission, alerts, status bar.
 */
export function GuidedTour() {
  const [visible, setVisible] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<Rect | null>(null);
  const [cardPos, setCardPos] = useState<{ top: number; left: number } | null>(null);

  const rafRef = useRef<number | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);

  const measureTarget = useCallback((index: number) => {
    const step = STEPS[index];
    if (!step) return;
    const el = document.querySelector<HTMLElement>(step.selector);
    if (!el) {
      // Target not found — skip with fallback.
      setTargetRect(null);
      setCardPos({ top: 80, left: window.innerWidth / 2 - CARD_W / 2 });
      return;
    }
    const rect = el.getBoundingClientRect();
    const r: Rect = {
      top: rect.top,
      left: rect.left,
      right: rect.right,
      bottom: rect.bottom,
      width: rect.width,
      height: rect.height,
    };
    setTargetRect(r);
    setCardPos(computeCardPosition(r, step.placement));
  }, []);

  // Re-measure on resize.
  useEffect(() => {
    if (!visible) return;
    function onResize() {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => measureTarget(stepIndex));
    }
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [visible, stepIndex, measureTarget]);

  // Check localStorage + listen for manual open.
  useEffect(() => {
    if (!localStorage.getItem(TOUR_KEY)) {
      // Slight delay so the shell layout has fully rendered.
      const id = window.setTimeout(() => {
        setStepIndex(0);
        setVisible(true);
        measureTarget(0);
      }, 800);
      return () => window.clearTimeout(id);
    }

    function onOpen() {
      setStepIndex(0);
      setVisible(true);
      measureTarget(0);
    }
    document.addEventListener("guided-tour-open", onOpen);
    return () => document.removeEventListener("guided-tour-open", onOpen);
  }, [measureTarget]);

  // Re-measure whenever step changes.
  useEffect(() => {
    if (visible) measureTarget(stepIndex);
  }, [stepIndex, visible, measureTarget]);

  // Card has tabIndex={-1} plus an onKeyDown handler for Escape/Arrow/Enter,
  // but tabIndex={-1} elements are never auto-focused by the browser — without
  // calling .focus() here, that handler never received a single keyboard
  // event, leaving keyboard-only users with no way to navigate or dismiss
  // the tour. Re-focus on every step change too, since the card's content
  // (and its accessible name) changes per step.
  useEffect(() => {
    if (visible) {
      cardRef.current?.focus();
    }
  }, [visible, stepIndex]);

  // Restore focus to whatever was focused before the tour opened, once it closes.
  useEffect(() => {
    if (!visible) {
      return undefined;
    }
    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    return () => {
      previouslyFocused?.focus();
    };
  }, [visible]);

  function dismiss() {
    localStorage.setItem(TOUR_KEY, "1");
    setVisible(false);
  }

  function next() {
    if (stepIndex < STEPS.length - 1) {
      setStepIndex((i) => i + 1);
    } else {
      dismiss();
    }
  }

  function prev() {
    if (stepIndex > 0) setStepIndex((i) => i - 1);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") dismiss();
    if (e.key === "ArrowRight" || e.key === "Enter") next();
    if (e.key === "ArrowLeft") prev();
  }

  if (!visible || !cardPos) return null;

  const step = STEPS[stepIndex];
  const vw = typeof window !== "undefined" ? window.innerWidth : 1440;
  const vh = typeof window !== "undefined" ? window.innerHeight : 900;

  // Spotlight: four strips surrounding the target (or full-screen if no target).
  const r = targetRect ?? { top: 0, left: 0, right: vw, bottom: 0, width: vw, height: 0 };
  const pad = 6;

  return (
    <>
      {/* Spotlight overlay — four strips that leave a hole around the target */}
      <div className="tour-overlay-top" style={{ top: 0, left: 0, right: 0, height: Math.max(0, r.top - pad) }} aria-hidden="true" />
      <div className="tour-overlay-bottom" style={{ top: r.bottom + pad, left: 0, right: 0, bottom: 0 }} aria-hidden="true" />
      <div className="tour-overlay-left" style={{ top: r.top - pad, left: 0, width: Math.max(0, r.left - pad), height: r.height + pad * 2 }} aria-hidden="true" />
      <div className="tour-overlay-right" style={{ top: r.top - pad, left: r.right + pad, right: 0, height: r.height + pad * 2 }} aria-hidden="true" />

      {/* Tour card */}
      <div
        ref={cardRef}
        className="tour-card"
        role="dialog"
        aria-modal="false"
        aria-label={`Guided tour step ${stepIndex + 1} of ${STEPS.length}`}
        style={{ top: cardPos.top, left: cardPos.left }}
        onKeyDown={handleKeyDown}
        tabIndex={-1}
      >
        <p className="tour-card-step">
          Step {stepIndex + 1} of {STEPS.length}
        </p>
        <h3 className="tour-card-title">{step.title}</h3>
        <p className="tour-card-body">{step.body}</p>

        {/* Progress dots */}
        <div className="tour-card-dots" aria-hidden="true">
          {STEPS.map((_, i) => (
            <span key={i} className={`tour-card-dot${i === stepIndex ? " active" : ""}`} />
          ))}
        </div>

        <div className="tour-card-nav">
          <button
            type="button"
            className="secondary-button"
            onClick={dismiss}
          >
            Skip tour
          </button>
          <div style={{ flex: 1 }} />
          {stepIndex > 0 && (
            <button type="button" className="secondary-button" onClick={prev}>
              ← Back
            </button>
          )}
          <button type="button" className="primary-button" onClick={next}>
            {stepIndex < STEPS.length - 1 ? "Next →" : "Finish ✓"}
          </button>
        </div>
      </div>
    </>
  );
}
