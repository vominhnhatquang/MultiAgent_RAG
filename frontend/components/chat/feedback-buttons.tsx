"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ThumbsUp, ThumbsDown } from "lucide-react";

interface FeedbackButtonsProps {
  messageId: string;
  sessionId: string;
  onFeedback: (sessionId: string, messageId: string, rating: "thumbs_up" | "thumbs_down", comment?: string) => void;
}

export function FeedbackButtons({ messageId, sessionId, onFeedback }: FeedbackButtonsProps) {
  const [rating, setRating] = useState<"thumbs_up" | "thumbs_down" | null>(null);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleRate = (newRating: "thumbs_up" | "thumbs_down") => {
    if (submitted) return;
    
    setRating(newRating);
    
    if (newRating === "thumbs_down") {
      setShowComment(true);
    } else {
      // Thumbs up - submit immediately
      onFeedback(sessionId, messageId, newRating);
      setSubmitted(true);
    }
  };

  const handleSubmitComment = () => {
    if (rating && !submitted) {
      onFeedback(sessionId, messageId, rating, comment.trim() || undefined);
      setSubmitted(true);
      setShowComment(false);
    }
  };

  const handleCancel = () => {
    setShowComment(false);
    setComment("");
    setRating(null);
  };

  if (submitted) {
    return (
      <span className="text-xs text-muted-foreground">
        Thanks for your feedback!
      </span>
    );
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            "h-7 w-7",
            rating === "thumbs_up" && "text-green-500 bg-green-500/10"
          )}
          onClick={() => handleRate("thumbs_up")}
          disabled={submitted}
        >
          <ThumbsUp className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            "h-7 w-7",
            rating === "thumbs_down" && "text-red-500 bg-red-500/10"
          )}
          onClick={() => handleRate("thumbs_down")}
          disabled={submitted}
        >
          <ThumbsDown className="h-3.5 w-3.5" />
        </Button>
      </div>

      {showComment && (
        <div className="w-64 space-y-2">
          <Textarea
            placeholder="What went wrong? (optional)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="min-h-[60px] text-xs"
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs"
              onClick={handleCancel}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              className="h-7 text-xs"
              onClick={handleSubmitComment}
            >
              Submit
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
