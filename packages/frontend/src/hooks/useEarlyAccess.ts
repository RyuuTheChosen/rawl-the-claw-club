"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

const STORAGE_KEY = "rawl_waitlist_email";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function useEarlyAccess() {
  const [email, setEmail] = useState("");
  const [isSubmitted, setIsSubmitted] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) setIsSubmitted(true);
    } catch {
      // SSR or storage unavailable
    }
  }, []);

  const submit = useCallback(() => {
    const trimmed = email.trim();
    if (!EMAIL_RE.test(trimmed)) {
      toast.error("Enter a valid email address");
      return;
    }
    try {
      localStorage.setItem(STORAGE_KEY, trimmed);
    } catch {
      // storage full — still show success
    }
    setIsSubmitted(true);
    setEmail("");
    toast.success("You're on the list! We'll be in touch.");
  }, [email]);

  return { email, setEmail, isSubmitted, submit } as const;
}
