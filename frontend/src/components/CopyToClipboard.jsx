import toast from 'react-hot-toast';

function CopyToClipboard({ text, className, children }) {
  const handleCopy = (event) => {
    event.stopPropagation();

    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(() => {
        toast.success('链接已复制到剪贴板');
      }, (error) => {
        toast.error('无法通过安全API复制链接');
        console.error('Could not copy text using navigator.clipboard: ', error);
      });
      return;
    }

    try {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.top = '-9999px';
      textArea.style.left = '-9999px';

      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();

      document.execCommand('copy');
      document.body.removeChild(textArea);

      toast.success('链接已复制到剪贴板');
    } catch (error) {
      toast.error('无法复制链接');
      console.error('Could not copy text using fallback method: ', error);
    }
  };

  return (
    <button onClick={handleCopy} className={className}>
      {children}
    </button>
  );
}

export default CopyToClipboard;
