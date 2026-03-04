import Editor from '@/components/Editor';
import Timeline from '@/components/Timeline';

export default function Home() {
    return (
        <main className="flex min-h-screen flex-col items-center justify-between p-24 bg-slate-50">
            <div className="z-10 max-w-5xl w-full items-center justify-between font-mono text-sm flex mb-8">
                <h1 className="text-3xl font-bold text-slate-900">Clarion: The Experience</h1>
                <div className="flex gap-4">
                    <button className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition">Intake Evidence</button>
                    <button className="px-4 py-2 border border-slate-300 text-slate-700 rounded-md hover:bg-slate-100 transition">Export PDF</button>
                </div>
            </div>

            <div className="flex-1 w-full max-w-5xl flex gap-8">
                <div className="flex-1">
                    <Editor />
                </div>
                <aside className="w-80 bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
                    <h2 className="font-semibold text-slate-800 mb-4">Evidence & Citations</h2>
                    <div className="space-y-2 text-xs text-slate-500 italic">
                        Upload documents to see citations and contradictions.
                    </div>
                </aside>
            </div>

            <Timeline />
        </main>
    );
}
