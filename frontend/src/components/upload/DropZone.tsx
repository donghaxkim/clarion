"use client";

import { useState, useCallback } from "react";
import { Upload, FileText, Image, Music, Video } from "lucide-react";
import { cn } from "@/lib/utils";

interface DropZoneProps {
  onFiles: (files: File[]) => void;
  isDisabled?: boolean;
}

const ACCEPTED_TYPES = [
  { ext: "PDF", icon: FileText, color: "text-gold-400" },
  { ext: "JPG", icon: Image, color: "text-indigo-400" },
  { ext: "PNG", icon: Image, color: "text-indigo-400" },
  { ext: "MP3", icon: Music, color: "text-success" },
  { ext: "WAV", icon: Music, color: "text-success" },
  { ext: "MP4", icon: Video, color: "text-amber-400" },
];

export function DropZone({ onFiles, isDisabled }: DropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      if (isDisabled) return;
      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) onFiles(files);
    },
    [onFiles, isDisabled]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? []);
      if (files.length > 0) onFiles(files);
      e.target.value = "";
    },
    [onFiles]
  );

  return (
    <label
      className={cn(
        "relative flex flex-col items-center justify-center gap-3 shrink-0",
        "rounded border-2 border-dashed cursor-pointer",
        "px-6 py-8 text-center transition-all duration-200 min-h-[140px]",
        isDragOver
          ? "border-gold-500 bg-gold-500/5 shadow-glow-gold"
          : "border-border hover:border-gold-500/40 hover:bg-surface-raised",
        isDisabled && "opacity-40 pointer-events-none"
      )}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      <input
        type="file"
        multiple
        className="sr-only"
        onChange={handleInputChange}
        accept=".pdf,.jpg,.jpeg,.png,.mp3,.wav,.mp4"
        disabled={isDisabled}
      />

      <div
        className={cn(
          "w-10 h-10 rounded flex items-center justify-center transition-all duration-200",
          isDragOver
            ? "bg-gold-500/20 text-gold-400"
            : "bg-surface-raised text-text-muted"
        )}
      >
        <Upload className="w-5 h-5" />
      </div>

      <div>
        <p className="text-sm font-medium text-text-primary">
          {isDragOver ? "Drop files here" : "Drop evidence files here"}
        </p>
        <p className="text-xs text-text-muted mt-0.5">or click to browse</p>
      </div>

      <div className="flex flex-wrap justify-center gap-1.5">
        {ACCEPTED_TYPES.map(({ ext, icon: Icon, color }) => (
          <span
            key={ext}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface border border-border text-[10px] font-semibold text-text-muted"
          >
            <Icon className={cn("w-2.5 h-2.5", color)} />
            {ext}
          </span>
        ))}
      </div>
    </label>
  );
}
