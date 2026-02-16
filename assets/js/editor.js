import { Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import Link from '@tiptap/extension-link';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import TextStyle from '@tiptap/extension-text-style';
import Color from '@tiptap/extension-color';

function initEditor() {
  const textarea = document.getElementById('id_body');
  if (!textarea) return;

  const wrapper = document.createElement('div');
  wrapper.className = 'tiptap-wrapper';

  const toolbar = document.createElement('div');
  toolbar.className = 'tiptap-toolbar';

  const editorEl = document.createElement('div');
  editorEl.id = 'tiptap-body';
  editorEl.className = 'tiptap-editor';

  textarea.style.display = 'none';
  textarea.parentNode.insertBefore(wrapper, textarea.nextSibling);
  wrapper.appendChild(toolbar);
  wrapper.appendChild(editorEl);

  const icons = {
    paragraph: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M5 7.5c0-2.1 1.7-3.5 4-3.5h7v2H13v13h-2V6h-2c-1 0-2 .6-2 1.5S8 9 9 9h2v2H9c-2.3 0-4-1.4-4-3.5Z"/></svg>',
    h2: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 5h2v6h8V5h2v14h-2v-6H8v6H6V5Z"/></svg>',
    h3: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M5 5h2v6h5V5h2v14h-2v-6H7v6H5V5Zm9.5 6.2c0-1.3 1.1-2.2 2.5-2.2 1 0 1.9.5 2.3 1.3l-1.6.8c-.1-.3-.4-.6-.7-.6-.5 0-.8.3-.8.7 0 .4.3.7.8.7h.9v1.6h-.9c-.4 0-.7.2-.7.6 0 .4.3.7.8.7.3 0 .6-.3.7-.6l1.6.8c-.4.8-1.3 1.3-2.3 1.3-1.4 0-2.5-.9-2.5-2.2 0-.6.3-1.2.8-1.6-.5-.4-.8-1-.8-1.5Z"/></svg>',
    h4: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 5h2v6h5V5h2v14h-2v-6H8v6H6V5Zm10.5 7.5h1.5V10h2v2.5H22V14h-2v5h-2v-5h-1.5v-1.5Z"/></svg>',
    bold: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 5h6a4 4 0 0 1 0 8H7V5Zm2 2v4h4a2 2 0 0 0 0-4H9Zm-2 6h7a3 3 0 1 1 0 6H7v-6Zm2 2v2h5a1 1 0 1 0 0-2H9Z"/></svg>',
    italic: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M10 5h7v2h-2.8l-3.4 10H14v2H7v-2h2.8l3.4-10H10V5Z"/></svg>',
    underline: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 4h2v7a4 4 0 1 0 8 0V4h2v7a6 6 0 1 1-12 0V4Zm-1 16h14v2H5v-2Z"/></svg>',
    strike: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M5 5h14v2H5V5Zm2.5 6h3.7c.6.3 1 .6 1 .9 0 .5-.6.8-1.8.8-2.3 0-4.4 1-4.4 3.2 0 1.4 1 2.6 2.7 3.1V19c-.6-.4-.9-.9-.9-1.4 0-1 .9-1.6 2.6-1.6 1.2 0 2.2-.2 3-.6h3.6v-2H7.5V11Z"/></svg>',
    link: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="m12.8 6.7 1.4-1.4a4 4 0 0 1 5.7 5.7l-2.5 2.5a4 4 0 0 1-5.7 0l-1.1-1.1 1.4-1.4 1.1 1.1a2 2 0 0 0 2.8 0l2.5-2.5a2 2 0 0 0-2.8-2.8l-1.4 1.4-1.4-1.4Zm-1.6 10.6-1.4 1.4a4 4 0 0 1-5.7-5.7l2.5-2.5a4 4 0 0 1 5.7 0l1.1 1.1-1.4 1.4-1.1-1.1a2 2 0 0 0-2.8 0l-2.5 2.5a2 2 0 0 0 2.8 2.8l1.4-1.4 1.4 1.4Z"/></svg>',
    clear: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 6h12v2H6V6Zm2 4h8v2H8v-2Zm-2 4h12v2H6v-2Z"/></svg>',
    bullet: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 7.5A1.5 1.5 0 1 1 9 7.5 1.5 1.5 0 0 1 6 7.5Zm0 5A1.5 1.5 0 1 1 9 12.5 1.5 1.5 0 0 1 6 12.5Zm0 5A1.5 1.5 0 1 1 9 17.5 1.5 1.5 0 0 1 6 17.5Zm4-12h8v2h-8V5.5Zm0 5h8v2h-8v-2Zm0 5h8v2h-8v-2Z"/></svg>',
    number: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7.5 6h2v2H11v2H9.5v2h-2V10H6V8h1.5V6Zm0 6h2v2H11v2H9.5v2h-2v-2H6v-2h1.5v-2Zm7-6h2v2H16v2h-1.5V8H13V6h1.5Zm0 6h2v2H16v2h-1.5v-2H13v-2h1.5Z"/></svg>',
    quote: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 7h6v10H6V7Zm6 0h6v10h-6V7Zm-4 2v6h2V9H8Zm6 0v6h2V9h-2Z"/></svg>',
    code: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="m9.4 7 1.9.7L9.6 17l-1.9-.7L9.4 7Zm-5 4.5L8 7.8l1.4 1.4-3 3 3 3L8 16.6 4.4 12Zm10.2 0 3.6 4.6-1.4 1.4-3-3-3 3-1.4-1.4 3.6-4.6-3.6-4.6L10.8 7l3 3 3-3 1.4 1.4-3.6 4.6Z"/></svg>',
    hr: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M4 11h16v2H4v-2Z"/></svg>',
    left: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M5 7h14v2H5V7Zm0 4h10v2H5v-2Zm0 4h14v2H5v-2Z"/></svg>',
    center: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 7h18v2H3V7Zm3 4h12v2H6v-2Zm-3 4h18v2H3v-2Z"/></svg>',
    right: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M5 7h14v2H5V7Zm4 4h10v2H9v-2Zm-4 4h14v2H5v-2Z"/></svg>',
    undo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7.8 7.2 4 11l3.8 3.8 1.4-1.4-1.4-1.4H13a4 4 0 0 1 0 8h-2v2h2a6 6 0 0 0 0-12H7.8l1.4-1.4-1.4-1.4Z"/></svg>',
    redo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="m16.2 7.2 3.8 3.8-3.8 3.8-1.4-1.4 1.4-1.4H11a4 4 0 0 0 0 8h2v2h-2a6 6 0 0 1 0-12h5.2l-1.4-1.4 1.4-1.4Z"/></svg>',
    color: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 4a7 7 0 0 0-7 7c0 3 2 5.7 4.6 6.6.7.2 1.4-.3 1.4-1l-.1-1c0-.6-.5-1.1-1.1-1.2-1-.2-1.8-1.4-1.8-2.4A3 3 0 0 1 12 9h5a3 3 0 0 1 0 6h-.5a1 1 0 0 0-.9.6l-.5 1.2a1 1 0 0 0 .6 1.3A7 7 0 0 0 12 4Z"/></svg>',
  };

  const editor = new Editor({
    element: editorEl,
    extensions: [
      Color.configure({ types: ['textStyle'] }),
      TextStyle,
      Underline,
      Link.configure({ openOnClick: false, autolink: true, linkOnPaste: true }),
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      StarterKit.configure({ heading: { levels: [2, 3, 4] } }),
      Placeholder.configure({ placeholder: 'Write your post body here...' })
    ],
    content: textarea.value?.trim() ? textarea.value : '<p></p>',
    onUpdate: ({ editor }) => {
      textarea.value = editor.getHTML();
    },
  });

  window.__tiptapEditor = editor;

  let paletteVisible = false;

  const buttons = [
    {
      label: 'P',
      icon: icons.paragraph,
      title: 'Paragraph',
      run: () => editor.chain().focus().setParagraph().run(),
      isActive: () => editor.isActive('paragraph'),
    },
    {
      label: 'H2',
      icon: icons.h2,
      title: 'Heading 2',
      run: () => editor.chain().focus().toggleHeading({ level: 2 }).run(),
      isActive: () => editor.isActive('heading', { level: 2 }),
    },
    {
      label: 'H3',
      icon: icons.h3,
      title: 'Heading 3',
      run: () => editor.chain().focus().toggleHeading({ level: 3 }).run(),
      isActive: () => editor.isActive('heading', { level: 3 }),
    },
    {
      label: 'H4',
      icon: icons.h4,
      title: 'Heading 4',
      run: () => editor.chain().focus().toggleHeading({ level: 4 }).run(),
      isActive: () => editor.isActive('heading', { level: 4 }),
    },
    {
      label: 'Bold',
      icon: icons.bold,
      title: 'Bold',
      run: () => editor.chain().focus().toggleBold().run(),
      isActive: () => editor.isActive('bold'),
    },
    {
      label: 'Italic',
      icon: icons.italic,
      title: 'Italic',
      run: () => editor.chain().focus().toggleItalic().run(),
      isActive: () => editor.isActive('italic'),
    },
    {
      label: 'Underline',
      icon: icons.underline,
      title: 'Underline',
      run: () => editor.chain().focus().toggleUnderline().run(),
      isActive: () => editor.isActive('underline'),
    },
    {
      label: 'Strike',
      icon: icons.strike,
      title: 'Strikethrough',
      run: () => editor.chain().focus().toggleStrike().run(),
      isActive: () => editor.isActive('strike'),
    },
    {
      label: 'Link',
      icon: icons.link,
      title: 'Add or edit link',
      run: () => {
        const previousUrl = editor.getAttributes('link').href || 'https://';
        const url = window.prompt('Enter URL', previousUrl);
        if (url === null) return;
        if (!url || url.trim() === '') {
          editor.chain().focus().unsetLink().run();
          return;
        }
        editor.chain().focus().setLink({ href: url.trim() }).run();
      },
      isActive: () => editor.isActive('link'),
    },
    {
      label: 'Clear',
      icon: icons.clear,
      title: 'Clear formatting',
      run: () => editor.chain().focus().unsetAllMarks().clearNodes().run(),
      isActive: () => false,
    },
    {
      label: 'Color',
      icon: icons.color,
      title: 'Text color',
      run: () => {
        paletteVisible = !paletteVisible;
        togglePalette();
      },
      isActive: () => paletteVisible,
    },
    {
      label: 'Bullet',
      icon: icons.bullet,
      title: 'Bullet list',
      run: () => editor.chain().focus().toggleBulletList().run(),
      isActive: () => editor.isActive('bulletList'),
    },
    {
      label: 'Number',
      icon: icons.number,
      title: 'Numbered list',
      run: () => editor.chain().focus().toggleOrderedList().run(),
      isActive: () => editor.isActive('orderedList'),
    },
    {
      label: 'Quote',
      icon: icons.quote,
      title: 'Block quote',
      run: () => editor.chain().focus().toggleBlockquote().run(),
      isActive: () => editor.isActive('blockquote'),
    },
    {
      label: 'Code',
      icon: icons.code,
      title: 'Code block',
      run: () => editor.chain().focus().toggleCodeBlock().run(),
      isActive: () => editor.isActive('codeBlock'),
    },
    {
      label: 'HR',
      icon: icons.hr,
      title: 'Horizontal rule',
      run: () => editor.chain().focus().setHorizontalRule().run(),
      isActive: () => false,
    },
    {
      label: 'Left',
      icon: icons.left,
      title: 'Align left',
      run: () => editor.chain().focus().setTextAlign('left').run(),
      isActive: () => editor.isActive({ textAlign: 'left' }),
    },
    {
      label: 'Center',
      icon: icons.center,
      title: 'Align center',
      run: () => editor.chain().focus().setTextAlign('center').run(),
      isActive: () => editor.isActive({ textAlign: 'center' }),
    },
    {
      label: 'Right',
      icon: icons.right,
      title: 'Align right',
      run: () => editor.chain().focus().setTextAlign('right').run(),
      isActive: () => editor.isActive({ textAlign: 'right' }),
    },
    {
      label: 'Undo',
      icon: icons.undo,
      title: 'Undo',
      run: () => editor.chain().focus().undo().run(),
      isActive: () => false,
    },
    {
      label: 'Redo',
      icon: icons.redo,
      title: 'Redo',
      run: () => editor.chain().focus().redo().run(),
      isActive: () => false,
    },
  ];

  const buttonElements = buttons.map((cfg) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'tiptap-btn';
    btn.innerHTML = cfg.icon || cfg.label;
    btn.title = cfg.title;
    btn.setAttribute('aria-label', cfg.title);
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      cfg.run();
      updateActive();
    });
    toolbar.appendChild(btn);
    return { btn, isActive: cfg.isActive };
  });

  const swatches = [
    { name: 'Ocean', value: '#0f3f46' },
    { name: 'Emerald', value: '#3C9C64' },
    { name: 'Sky', value: '#0ea5e9' },
    { name: 'Gold', value: '#eab308' },
    { name: 'Rose', value: '#ef4444' },
    { name: 'Ink', value: '#111827' },
  ];

  const swatchRow = document.createElement('div');
  swatchRow.className = 'tiptap-swatches';
  toolbar.appendChild(swatchRow);

  const swatchButtons = swatches.map((swatch) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'tiptap-swatch';
    btn.title = `${swatch.name} color`;
    btn.style.backgroundColor = swatch.value;
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const current = editor.getAttributes('textStyle').color;
      if (current && current.toLowerCase() === swatch.value.toLowerCase()) {
        editor.chain().focus().unsetColor().run();
      } else {
        editor.chain().focus().setColor(swatch.value).run();
      }
      updateActive();
    });
    swatchRow.appendChild(btn);
    return { btn, value: swatch.value };
  });

  const clearColor = document.createElement('button');
  clearColor.type = 'button';
  clearColor.className = 'tiptap-btn';
  clearColor.textContent = 'Clear color';
  clearColor.title = 'Remove text color';
  clearColor.addEventListener('click', (e) => {
    e.preventDefault();
    editor.chain().focus().unsetColor().run();
    updateActive();
  });
  toolbar.appendChild(clearColor);

  function updateActive() {
    buttonElements.forEach(({ btn, isActive }) => {
      btn.classList.toggle('is-active', Boolean(isActive && isActive()))
    });
    const currentColor = (editor.getAttributes('textStyle').color || '').toLowerCase();
    swatchButtons.forEach(({ btn, value }) => {
      btn.classList.toggle('is-active', currentColor === value.toLowerCase());
    });
    textarea.value = editor.getHTML();
  }

  function togglePalette() {
    if (paletteVisible) {
      swatchRow.classList.remove('is-hidden');
    } else {
      swatchRow.classList.add('is-hidden');
    }
  }

  editor.on('selectionUpdate', updateActive);
  editor.on('update', updateActive);
  updateActive();
  togglePalette();

  const form = textarea.closest('form');
  if (form) {
    form.addEventListener('submit', () => {
      textarea.value = editor.getHTML();
    });
  }
}

document.addEventListener('DOMContentLoaded', initEditor);