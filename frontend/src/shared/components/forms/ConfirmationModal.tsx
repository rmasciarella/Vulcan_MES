"use client";

import React from "react";

interface ConfirmationModalProps {
  title: string;
  getImpactDetails?: () => Promise<Record<string, unknown>> | Promise<void> | void;
  onCancel: () => void;
  onConfirm: () => Promise<void> | void;
}

export function ConfirmationModal(props: ConfirmationModalProps) {
  const [step, setStep] = React.useState(1);
  const [seconds, setSeconds] = React.useState(5);
  const [impact, setImpact] = React.useState<Record<string, unknown> | null>(null);
  const [loadingImpact, setLoadingImpact] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    let mounted = true;
    (async () => {
      if (!props.getImpactDetails) return;
      setLoadingImpact(true);
      try {
        const data = (await props.getImpactDetails()) as Record<string, unknown> | void;
        if (mounted && data && typeof data === "object") setImpact(data);
      } finally {
        if (mounted) setLoadingImpact(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [props.getImpactDetails]);

  React.useEffect(() => {
    if (step !== 2) return;
    setSeconds(5);
    const id = setInterval(() => {
      setSeconds((s) => (s > 0 ? s - 1 : 0));
    }, 1000);
    return () => clearInterval(id);
  }, [step]);

  const canProceedToStep2 = step === 1; // could add checkboxes/acknowledgements
  const canConfirm = step === 2 && seconds === 0 && !submitting;

  const handleNext = () => setStep(2);
  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await props.onConfirm();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4">
      <div className="bg-white rounded shadow w-full max-w-lg p-4 space-y-4">
        <div className="text-lg font-semibold">{props.title}</div>
        <div className="text-sm text-gray-600">
          This is a destructive action. Please review the impact and confirm.
        </div>

        {step === 1 && (
          <div className="space-y-3">
            <div className="text-sm">Impact summary:</div>
            <div className="border rounded p-2 bg-gray-50 text-xs min-h-16">
              {loadingImpact && <div>Loading impact…</div>}
              {!loadingImpact && !impact && <div>No additional details available.</div>}
              {!loadingImpact && impact && (
                <ul className="list-disc ml-4">
                  {Object.entries(impact).map(([k, v]) => (
                    <li key={k}>
                      <span className="font-mono">{k}</span>: {String(v)}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="flex items-center justify-end gap-2">
              <button className="border rounded px-3 py-1" onClick={props.onCancel} disabled={submitting}>
                Cancel
              </button>
              <button
                className="border rounded px-3 py-1 bg-red-600 text-white disabled:opacity-50"
                onClick={handleNext}
                disabled={!canProceedToStep2}
              >
                Continue
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            <div className="text-sm">
              Final confirmation: This action cannot be undone. Please wait for the countdown to
              finish before confirming.
            </div>
            <div className="text-3xl font-mono text-center">{seconds}</div>
            <div className="flex items-center justify-end gap-2">
              <button className="border rounded px-3 py-1" onClick={props.onCancel} disabled={submitting}>
                Cancel
              </button>
              <button
                className="border rounded px-3 py-1 bg-red-700 text-white disabled:opacity-50"
                disabled={!canConfirm}
                onClick={handleConfirm}
              >
                {submitting ? "Processing..." : "Confirm"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}