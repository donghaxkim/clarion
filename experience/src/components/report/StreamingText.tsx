'use client';

import React, { useState, useEffect, useRef } from 'react';

interface StreamingTextProps {
  text: string;
  streaming: boolean;
  className?: string;
  style?: React.CSSProperties;
}

export function StreamingText({ text, streaming, className, style }: StreamingTextProps) {
  return (
    <span className={className} style={style}>
      {text}
      {streaming && <span className="streaming-cursor" aria-hidden />}
    </span>
  );
}
