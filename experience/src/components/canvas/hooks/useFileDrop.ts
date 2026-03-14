'use client';

import { useCallback, useRef, useState } from 'react';
import { useReactFlow } from '@xyflow/react';

export interface UseFileDropOptions {
  onFiles: (files: File[], position: { x: number; y: number }) => void;
}

export function useFileDrop({ onFiles }: UseFileDropOptions) {
  const { screenToFlowPosition } = useReactFlow();
  const [isDragOver, setIsDragOver] = useState(false);
  const [dropLabelPos, setDropLabelPos] = useState({ x: 0, y: 0 });
  const dragCounterRef = useRef(0);

  const onDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current++;
    if (e.dataTransfer.types.includes('Files')) {
      setIsDragOver(true);
    }
  }, []);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.types.includes('Files')) {
      e.dataTransfer.dropEffect = 'copy';
      setDropLabelPos({ x: e.clientX, y: e.clientY });
    }
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0;
      setIsDragOver(false);
    }
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounterRef.current = 0;
      setIsDragOver(false);

      const files = Array.from(e.dataTransfer.files);
      if (files.length === 0) return;

      // Convert screen coordinates to flow coordinates
      const flowPos = screenToFlowPosition({ x: e.clientX, y: e.clientY });
      onFiles(files, flowPos);
    },
    [onFiles, screenToFlowPosition]
  );

  return {
    isDragOver,
    dropLabelPos,
    handlers: { onDragEnter, onDragOver, onDragLeave, onDrop },
  };
}
