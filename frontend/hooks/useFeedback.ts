"use client";

import { useState, useCallback } from "react";
import { api } from "@/lib/api";

interface FeedbackState {
  [messageId: string]: "thumbs_up" | "thumbs_down" | null;
}

interface UseFeedbackReturn {
  feedbackState: FeedbackState;
  isSubmitting: boolean;
  error: string | null;
  submitFeedback: (sessionId: string, messageId: string, rating: "thumbs_up" | "thumbs_down", comment?: string) => Promise<void>;
  hasFeedback: (messageId: string) => boolean;
  getFeedback: (messageId: string) => "thumbs_up" | "thumbs_down" | null;
  clearError: () => void;
}

export function useFeedback(): UseFeedbackReturn {
  const [feedbackState, setFeedbackState] = useState<FeedbackState>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submitFeedback = useCallback(
    async (sessionId: string, messageId: string, rating: "thumbs_up" | "thumbs_down", comment?: string) => {
      // Don't submit if already voted
      if (feedbackState[messageId]) {
        return;
      }

      setIsSubmitting(true);
      setError(null);

      try {
        await api.sendFeedback(sessionId, messageId, rating, comment);
        setFeedbackState((prev) => ({ ...prev, [messageId]: rating }));
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to submit feedback";
        setError(message);
      } finally {
        setIsSubmitting(false);
      }
    },
    [feedbackState]
  );

  const hasFeedback = useCallback(
    (messageId: string) => {
      return !!feedbackState[messageId];
    },
    [feedbackState]
  );

  const getFeedback = useCallback(
    (messageId: string) => {
      return feedbackState[messageId] || null;
    },
    [feedbackState]
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    feedbackState,
    isSubmitting,
    error,
    submitFeedback,
    hasFeedback,
    getFeedback,
    clearError,
  };
}
