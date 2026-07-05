import React, { useRef, useState } from 'react';
import {
  Check,
  ImagePlus,
  Palette,
  RotateCcw,
  SlidersHorizontal,
  Trash2,
  Type,
  X,
} from 'lucide-react';

const MAX_BACKGROUND_SIZE = 5 * 1024 * 1024;
const ACCEPTED_BACKGROUND_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function AppearanceRange({ label, value, min, max, step = 1, suffix = '', onChange }) {
  return (
    <label className="appearance-control">
      <span>{label}</span>
      <div className="appearance-range-row">
        <input
          type="range"
          className="form-range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={event => onChange(Number(event.target.value))}
        />
        <strong>{value}{suffix}</strong>
      </div>
    </label>
  );
}

function SegmentedChoice({ label, value, options, onChange }) {
  return (
    <div className="appearance-control">
      <span>{label}</span>
      <div className="appearance-segmented">
        {options.map(option => (
          <button
            key={option.value}
            type="button"
            className={value === option.value ? 'active' : ''}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function AppearancePanel({
  open,
  onClose,
  theme,
  appearance,
  skinPresets,
  accentSwatches,
  onToggleTheme,
  onApplySkinPreset,
  onSetAppearance,
  onSaveBackgroundImage,
  onRemoveBackgroundImage,
  onResetAppearance,
}) {
  const fileInputRef = useRef(null);
  const [error, setError] = useState('');
  const [savingImage, setSavingImage] = useState(false);

  if (!open) return null;

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setError('');
    if (!ACCEPTED_BACKGROUND_TYPES.includes(file.type)) {
      setError('仅支持 JPG、PNG 或 WebP 图片。');
      return;
    }
    if (file.size > MAX_BACKGROUND_SIZE) {
      setError('背景图片不能超过 5MB。');
      return;
    }
    try {
      setSavingImage(true);
      const dataUrl = await readFileAsDataUrl(file);
      await onSaveBackgroundImage(file, dataUrl);
    } catch {
      setError('背景图片保存失败，请换一张图片重试。');
    } finally {
      setSavingImage(false);
    }
  };

  const removeBackground = async () => {
    setError('');
    await onRemoveBackgroundImage();
  };

  const resetAppearance = async () => {
    setError('');
    await onResetAppearance();
  };

  return (
    <div className="appearance-overlay" role="presentation" onClick={onClose}>
      <aside className="appearance-panel" role="dialog" aria-modal="true" aria-label="外观设置" onClick={event => event.stopPropagation()}>
        <header className="appearance-panel-header">
          <div>
            <div className="appearance-eyebrow">Appearance</div>
            <h2>外观</h2>
          </div>
          <button type="button" className="appearance-icon-button" onClick={onClose} aria-label="关闭外观设置">
            <X size={18} />
          </button>
        </header>

        <section className="appearance-section">
          <div className="appearance-section-title">
            <Palette size={17} />
            <span>皮肤预设</span>
          </div>
          <div className="appearance-skin-grid">
            {skinPresets.map(preset => (
              <button
                key={preset.id}
                type="button"
                className={`appearance-skin-card skin-${preset.id} ${appearance.skinPreset === preset.id ? 'active' : ''}`.trim()}
                onClick={() => onApplySkinPreset(preset.id)}
              >
                <span className="appearance-skin-preview" aria-hidden="true">
                  <i></i>
                  <i></i>
                  <i></i>
                </span>
                <span className="appearance-skin-copy">
                  <strong>{preset.label}</strong>
                  <small>{preset.description}</small>
                </span>
                {appearance.skinPreset === preset.id && <Check size={16} />}
              </button>
            ))}
          </div>
        </section>

        <section className="appearance-section">
          <div className="appearance-section-title">
            <SlidersHorizontal size={17} />
            <span>颜色与界面</span>
          </div>
          <div className="appearance-accent-grid">
            {accentSwatches.map(color => (
              <button
                key={color}
                type="button"
                className={appearance.accentColor === color ? 'active' : ''}
                style={{ '--swatch-color': color }}
                onClick={() => onSetAppearance({ accentColor: color })}
                aria-label={`使用强调色 ${color}`}
              >
                {appearance.accentColor === color && <Check size={14} />}
              </button>
            ))}
            <label className="appearance-color-input" aria-label="自定义强调色">
              <input
                type="color"
                aria-label="选择自定义强调色"
                value={appearance.accentColor}
                onChange={event => onSetAppearance({ accentColor: event.target.value })}
              />
            </label>
          </div>
          <SegmentedChoice
            label="模式"
            value={theme}
            options={[
              { value: 'dark', label: '深色' },
              { value: 'light', label: '浅色' },
            ]}
            onChange={nextTheme => {
              if (nextTheme !== theme) onToggleTheme();
            }}
          />
          <SegmentedChoice
            label="密度"
            value={appearance.density}
            options={[
              { value: 'comfortable', label: '舒适' },
              { value: 'compact', label: '紧凑' },
            ]}
            onChange={density => onSetAppearance({ density })}
          />
          <SegmentedChoice
            label="文字"
            value={appearance.contrastMode}
            options={[
              { value: 'standard', label: '标准' },
              { value: 'high', label: '高对比' },
            ]}
            onChange={contrastMode => onSetAppearance({ contrastMode })}
          />
        </section>

        <section className="appearance-section">
          <div className="appearance-section-title">
            <ImagePlus size={17} />
            <span>背景图片</span>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="d-none"
            onChange={handleFileChange}
          />
          <div className="appearance-background-actions">
            <button type="button" className="btn btn-primary" onClick={() => fileInputRef.current?.click()} disabled={savingImage}>
              <ImagePlus size={16} />
              {savingImage ? '保存中' : '上传背景'}
            </button>
            <button type="button" className="btn btn-outline-secondary" onClick={removeBackground} disabled={!appearance.hasBackgroundImage}>
              <Trash2 size={16} />
              删除
            </button>
          </div>
          {appearance.hasBackgroundImage && (
            <div className="appearance-background-name">{appearance.backgroundImageName || '自定义背景'}</div>
          )}
          {appearance.hasBackgroundImage && appearance.skinPreset === 'cinema' && (
            <div className="appearance-glass-note">已启用 Cinema Glass，背景会通过毛玻璃界面显示。</div>
          )}
          {error && <div className="appearance-error">{error}</div>}
          <AppearanceRange
            label="遮罩"
            value={appearance.backgroundOverlay}
            min={0}
            max={92}
            suffix="%"
            onChange={backgroundOverlay => onSetAppearance({ backgroundOverlay })}
          />
          <AppearanceRange
            label="模糊"
            value={appearance.backgroundBlur}
            min={0}
            max={20}
            suffix="px"
            onChange={backgroundBlur => onSetAppearance({ backgroundBlur })}
          />
          <AppearanceRange
            label="面板"
            value={appearance.surfaceOpacity}
            min={72}
            max={100}
            suffix="%"
            onChange={surfaceOpacity => onSetAppearance({ surfaceOpacity })}
          />
        </section>

        <footer className="appearance-panel-footer">
          <button type="button" className="btn btn-outline-secondary" onClick={resetAppearance}>
            <RotateCcw size={16} />
            恢复默认
          </button>
          <div className="appearance-note">
            <Type size={14} />
            配置仅保存在当前浏览器，不会修改 .env。
          </div>
        </footer>
      </aside>
    </div>
  );
}

export default AppearancePanel;
