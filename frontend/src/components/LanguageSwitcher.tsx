import { useTranslation } from 'react-i18next';
import { Globe } from 'lucide-react';

export const LanguageSwitcher = () => {
  const { i18n } = useTranslation();
  const isEn = i18n.language === 'en';

  const toggleLanguage = () => {
    i18n.changeLanguage(isEn ? 'zh' : 'en');
  };

  return (
    <button
      onClick={toggleLanguage}
      title={isEn ? 'Switch to 中文' : 'Switch to English'}
      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
    >
      <Globe size={13} />
      <span className="hidden xl:inline">{isEn ? '中文' : 'EN'}</span>
    </button>
  );
};
