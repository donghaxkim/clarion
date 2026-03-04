"use client";

import { motion } from 'framer-motion';

const Timeline = () => {
    return (
        <div className="w-full h-48 bg-slate-50 border-t border-slate-200 relative overflow-hidden flex items-center justify-center">
            <div className="text-slate-400 font-medium">Interactive Timeline (Framer Motion placeholder)</div>
            {/* Sample timeline nodes */}
            <motion.div
                className="absolute bottom-10 left-10 w-4 h-4 bg-blue-500 rounded-full cursor-pointer"
                whileHover={{ scale: 1.5 }}
            />
            <motion.div
                className="absolute bottom-10 left-1/2 w-4 h-4 bg-purple-500 rounded-full cursor-pointer"
                whileHover={{ scale: 1.5 }}
            />
        </div>
    );
};

export default Timeline;
