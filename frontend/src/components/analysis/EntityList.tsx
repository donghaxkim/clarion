"use client";

import { motion } from "framer-motion";
import { User, Car, MapPin, Building2, FileQuestion } from "lucide-react";
import { cn } from "@/lib/utils";
import type { EntityItem } from "@/lib/types";

function getEntityIcon(type: string) {
  const t = type.toLowerCase();
  if (t === "person") return User;
  if (t === "vehicle") return Car;
  if (t === "location") return MapPin;
  if (t === "organization") return Building2;
  return FileQuestion;
}

interface EntityListProps {
  entities: EntityItem[];
  onEntityClick?: (name: string) => void;
}

export function EntityList({ entities, onEntityClick }: EntityListProps) {
  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between gap-2 pb-3 border-b border-border">
        <h2 className="text-sm font-semibold text-text-primary">
          People & Things
        </h2>
        <span className="px-2 py-0.5 rounded bg-surface-raised border border-border text-[10px] font-semibold text-text-muted tabular-nums">
          {entities.length}
        </span>
      </div>
      <ul className="flex-1 overflow-y-auto space-y-1.5 pt-3">
        {entities.map((entity, i) => {
          const Icon = getEntityIcon(entity.type);
          const aliasCount = entity.aliases?.length ?? 0;
          return (
            <motion.li
              key={entity.name}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2, delay: i * 0.03 }}
              className={cn(
                "flex items-center gap-2.5 px-3 py-2 rounded border border-transparent",
                "hover:bg-surface-raised hover:border-border cursor-pointer transition-colors",
                onEntityClick && "cursor-pointer"
              )}
              onClick={() => onEntityClick?.(entity.name)}
            >
              <div className="w-8 h-8 rounded bg-surface-raised border border-border flex items-center justify-center flex-shrink-0">
                <Icon className="w-4 h-4 text-text-muted" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-text-primary truncate">
                  {entity.name}
                </p>
                {aliasCount > 0 && (
                  <p className="text-[10px] text-text-muted">
                    {aliasCount} alias{aliasCount !== 1 ? "es" : ""}
                  </p>
                )}
              </div>
            </motion.li>
          );
        })}
      </ul>
    </div>
  );
}
