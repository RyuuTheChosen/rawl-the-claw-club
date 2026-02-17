"use client";

import { type ReactNode, Children } from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";

interface StaggeredListProps {
  children: ReactNode;
  className?: string;
  staggerLimit?: number;
}

export function StaggeredList({
  children,
  className,
  staggerLimit = 12,
}: StaggeredListProps) {
  const items = Children.toArray(children);

  return (
    <div className={cn(className)}>
      {items.map((child, i) =>
        i < staggerLimit ? (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: i * 0.05 }}
          >
            {child}
          </motion.div>
        ) : (
          <motion.div
            key={i}
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.3 }}
          >
            {child}
          </motion.div>
        ),
      )}
    </div>
  );
}
