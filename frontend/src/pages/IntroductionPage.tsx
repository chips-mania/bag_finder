import React, { useState, useEffect } from 'react';
import './IntroductionPage.css';

const IntroductionPage: React.FC = () => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [shoppingMallIndex, setShoppingMallIndex] = useState(0);

  const bagImages = [
    { id: '1', imageUrl: '/home_imgs/home_bags/backpack.png' },
    { id: '2', imageUrl: '/home_imgs/home_bags/bosten_bag.png' },
    { id: '3', imageUrl: '/home_imgs/home_bags/clutch.png' },
    { id: '4', imageUrl: '/home_imgs/home_bags/cross_bag.png' },
    { id: '5', imageUrl: '/home_imgs/home_bags/eco_canvas_bag.png' },
    { id: '6', imageUrl: '/home_imgs/home_bags/shoulder_bag.png' },
    { id: '7', imageUrl: '/home_imgs/home_bags/tote_bag.png' },
    { id: '8', imageUrl: '/home_imgs/home_bags/waist_bag.png' }
  ];

  const shoppingMallImages = [
    { id: '1', imageUrl: '/home_imgs/shopping_mall_imgs/29cm.png' },
    { id: '2', imageUrl: '/home_imgs/shopping_mall_imgs/kream.png' },
    { id: '3', imageUrl: '/home_imgs/shopping_mall_imgs/musinsa.png' },
    { id: '4', imageUrl: '/home_imgs/shopping_mall_imgs/wconcept.png' },
    { id: '5', imageUrl: '/home_imgs/shopping_mall_imgs/zigzag.png' }
  ];

  const len = bagImages.length;

  // 자동 슬라이드
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % len);
    }, 5000);
    
    return () => clearInterval(interval);
  }, [len]);

  // 쇼핑몰 이미지 슬라이드 함수들
  const handlePrevMall = () => {
    setShoppingMallIndex((prev) => 
      prev === 0 ? shoppingMallImages.length - 1 : prev - 1
    );
  };

  const handleNextMall = () => {
    setShoppingMallIndex((prev) => 
      prev === shoppingMallImages.length - 1 ? 0 : prev + 1
    );
  };

  // 3D 변환 계산
  const getImageStyle = (index: number) => {
    let distance = index - currentIndex;
    
    // 순환 배열에서 최단 거리 계산
    if (distance > len / 2) {
      distance -= len;
    } else if (distance < -len / 2) {
      distance += len;
    }
    
    // 보이는 범위 제한 (-3, -2, -1, 0, 1, 2, 3) - 더 넓은 범위로 확장
    if (Math.abs(distance) > 3) {
      return { display: 'none' };
    }
    
    const isActive = distance === 0;
    const rotationY = 0;
    const translateX = distance * 220;
    const translateZ = isActive ? 0 : -60;
    
    // 거리에 따른 스케일과 투명도 조정
    let scale, opacity;
    if (isActive) {
      scale = 1;
      opacity = 1;
    } else if (Math.abs(distance) === 1) {
      scale = 0.8;
      opacity = 1;
    } else if (Math.abs(distance) === 2) {
      scale = 0.6;
      opacity = 1;
    } else { // distance === 3
      scale = 0.4;
      opacity = 0;
    }
    
    return {
      transform: `translateX(${translateX}px) translateZ(${translateZ}px) rotateY(${rotationY}deg) scale(${scale})`,
      opacity: opacity,
      zIndex: isActive ? 10 : 5 - Math.abs(distance)
    };
  };

  return (
    <div className="introduction-page">
      <h1 className="main-title">궁금한 가방을 찾아보세요.</h1>
      <div className="style-finder-image-container">
        <img 
          src="/home_imgs/home_sytle_finder.png" 
          alt="Style Finder" 
          className="style-finder-image"
        />
        <div className="bag-coverflow-container">
          <div className="bag-coverflow">
            {bagImages.map((image, index) => (
              <img
                key={image.id}
                src={image.imageUrl}
                alt={`Bag ${index + 1}`}
                className="coverflow-bag-image"
                style={getImageStyle(index)}
              />
            ))}
          </div>
        </div>
      </div>
      <div className="bottom-section">
        <div className="shopping-mall-slider">
          <button className="slider-arrow left" onClick={handlePrevMall}>
            ‹
          </button>
          <div className="shopping-mall-container">
            {shoppingMallImages.slice(shoppingMallIndex, shoppingMallIndex + 3).map((image, index) => (
              <img
                key={image.id}
                src={image.imageUrl}
                alt={`Shopping Mall ${shoppingMallIndex + index + 1}`}
                className="shopping-mall-image"
              />
            ))}
            {/* 3개 미만일 때 앞쪽 이미지들 보여주기 */}
            {shoppingMallIndex + 3 > shoppingMallImages.length && 
              shoppingMallImages.slice(0, (shoppingMallIndex + 3) - shoppingMallImages.length).map((image, index) => (
                <img
                  key={`wrap-${image.id}`}
                  src={image.imageUrl}
                  alt={`Shopping Mall ${index + 1}`}
                  className="shopping-mall-image"
                />
              ))
            }
          </div>
          <button className="slider-arrow right" onClick={handleNextMall}>
            ›
          </button>
        </div>
      </div>
    </div>
  );
};

export default IntroductionPage;
