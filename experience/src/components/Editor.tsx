"use client";

import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';

const TiptapEditor = () => {
    const editor = useEditor({
        extensions: [StarterKit],
        content: '<p>Start building your legal report here...</p>',
        editorProps: {
            attributes: {
                class: 'prose prose-sm sm:prose lg:prose-lg xl:prose-2xl focus:outline-none min-h-[400px]',
            },
        },
    });

    return (
        <div className="border border-slate-200 rounded-lg p-4 bg-white shadow-sm">
            <EditorContent editor={editor} />
        </div>
    );
};

export default TiptapEditor;
