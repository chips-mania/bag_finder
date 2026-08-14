import React, { useEffect, useState } from 'react';
import './Onboarding.css';

export const ONBOARDING_STORAGE_KEY = 'stylefinder-onboarding-complete';

const SAMPLE_BAGS = [
  { src: '/boston_bag/1.jpg', name: 'sample-1.jpg' },
  { src: '/boston_bag/4.jpg', name: 'sample-4.jpg' },
  { src: '/boston_bag/7.jpg', name: 'sample-7.jpg' },
  { src: '/boston_bag/10.jpg', name: 'sample-10.jpg' },
  { src: '/boston_bag/13.jpg', name: 'sample-13.jpg' },
  { src: '/boston_bag/16.jpg', name: 'sample-16.jpg' },
];

const STEPS = [
  {
    kicker: 'Step 1',
    title: '가방 사진을 고르세요',
    body: '갖고 싶은 가방 사진을 올리면 비슷한 제품을 찾아드려요. 아래에서 골라 바로 시작하거나, 직접 업로드해도 됩니다.',
  },
  {
    kicker: 'Step 2',
    title: '가방을 클릭하세요',
    body: '사진 속 가방 위를 클릭하면 윤곽이 잡힙니다. 잘못 잡히면 다시 클릭하거나 빼기 모드로 지울 수 있어요.',
  },
  {
    kicker: 'Step 3',
    title: 'SEARCH를 누르세요',
    body: '윤곽이 맞으면 SEARCH를 눌러 비슷한 가방을 찾습니다. 이후 색·종류·가격으로 더 좁힐 수 있어요.',
  },
  {
    kicker: 'Guide',
    title: '다시 보고 싶을 때',
    body: '다음에 이 안내를 보려면 상단 메뉴의 GUIDE를 누르세요.',
  },
];

interface OnboardingProps {
  open: boolean;
  hasSession: boolean;
  isUploading: boolean;
  onSelectSample: (src: string, filename: string) => Promise<void>;
  onFinished: () => void;
}

const Onboarding: React.FC<OnboardingProps> = ({
  open,
  hasSession,
  isUploading,
  onSelectSample,
  onFinished,
}) => {
  const [step, setStep] = useState(0);
  const [selectedSrc, setSelectedSrc] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setStep(0);
      setSelectedSrc(null);
    }
  }, [open]);

  if (!open) return null;

  const isBlocking = step === 0 || step === 3;
  const current = STEPS[step];

  const finish = () => {
    setStep(0);
    setSelectedSrc(null);
    onFinished();
  };

  const handleSkip = () => {
    if (step >= STEPS.length - 1) {
      finish();
      return;
    }
    setStep(STEPS.length - 1);
  };

  const handleNext = async () => {
    if (step === 0) {
      if (!selectedSrc) return;
      const sample = SAMPLE_BAGS.find((item) => item.src === selectedSrc);
      if (!sample) return;
      try {
        await onSelectSample(sample.src, sample.name);
        setStep(1);
      } catch {
        // 에러는 App에서 표시
      }
      return;
    }

    if (step >= STEPS.length - 1) {
      finish();
      return;
    }

    setStep((prev) => prev + 1);
  };

  const nextDisabled =
    isUploading ||
    (step === 0 && !selectedSrc) ||
    (step === 1 && !hasSession);

  return (
    <div className={`onboarding-layer ${isBlocking ? 'is-blocking' : 'is-pass-through'}`}>
      <div className="onboarding-box">
        <p className="onboarding-kicker">{current.kicker}</p>
        <h2>{current.title}</h2>
        <p>{current.body}</p>

        {step === 0 && (
          <div className="onboarding-samples">
            {SAMPLE_BAGS.map((sample) => (
              <button
                key={sample.src}
                type="button"
                className={`onboarding-sample ${selectedSrc === sample.src ? 'is-selected' : ''}`}
                disabled={isUploading}
                onClick={() => setSelectedSrc(sample.src)}
              >
                <img src={sample.src} alt="샘플 가방" />
              </button>
            ))}
          </div>
        )}

        <div className="onboarding-actions">
          <button type="button" className="onboarding-btn" onClick={handleSkip} disabled={isUploading}>
            Skip
          </button>
          <button
            type="button"
            className="onboarding-btn"
            onClick={handleNext}
            disabled={nextDisabled}
          >
            {step >= STEPS.length - 1 ? 'Done' : isUploading ? 'Uploading...' : 'Next'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Onboarding;
