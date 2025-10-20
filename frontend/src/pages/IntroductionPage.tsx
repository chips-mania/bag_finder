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
    { 
      id: '1', 
      imageUrl: '/home_imgs/shopping_mall_imgs/29cm.png',
      title: '29CM',
      description: '감도 깊은 취향 셀렉트샵'
    },
    { 
      id: '2', 
      imageUrl: '/home_imgs/shopping_mall_imgs/kream.png',
      title: '크림',
      description: 'KICK THE RULES, LEAD THE TREND'
    },
    { 
      id: '3', 
      imageUrl: '/home_imgs/shopping_mall_imgs/musinsa.png',
      title: '무신사',
      description: '패션의 모든 것, 다 무신사랑 해 !'
    },
    { 
      id: '4', 
      imageUrl: '/home_imgs/shopping_mall_imgs/wconcept.png',
      title: '더블유컨셉',
      description: '나만의컨셉, 감각적 스타일링'
    },
    { 
      id: '5', 
      imageUrl: '/home_imgs/shopping_mall_imgs/zigzag.png',
      title: '지그재그',
      description: '나를 표현하는 쇼핑, 지그재그'
    }
  ];

  const len = bagImages.length;

  // 자동 슬라이드
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % len);
    }, 3000);
    
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
                <div key={image.id} className="shopping-mall-item">
                  <img
                    src={image.imageUrl}
                    alt={`Shopping Mall ${shoppingMallIndex + index + 1}`}
                    className="shopping-mall-image"
                  />
                  <div className="shopping-mall-overlay">
                    <h3 className="shopping-mall-title">{image.title}</h3>
                    <p className="shopping-mall-description">{image.description}</p>
                  </div>
                </div>
              ))}
              {/* 3개 미만일 때 앞쪽 이미지들 보여주기 */}
              {shoppingMallIndex + 3 > shoppingMallImages.length && 
                shoppingMallImages.slice(0, (shoppingMallIndex + 3) - shoppingMallImages.length).map((image, index) => (
                  <div key={`wrap-${image.id}`} className="shopping-mall-item">
                    <img
                      src={image.imageUrl}
                      alt={`Shopping Mall ${index + 1}`}
                      className="shopping-mall-image"
                    />
                    <div className="shopping-mall-overlay">
                      <h3 className="shopping-mall-title">{image.title}</h3>
                      <p className="shopping-mall-description">{image.description}</p>
                    </div>
                  </div>
                ))
              }
            </div>
          <button className="slider-arrow right" onClick={handleNextMall}>
            ›
          </button>
        </div>
      </div>
      
      {/* 올해의 컬러 섹션 */}
      <div className="color-of-year-section">
        <div className="color-of-year-content">
          <h2 className="color-of-year-title">2025 올해의 컬러, 이 가방은 어떠신가요?</h2>
          
          <div className="color-showcase">
            <div className="color-image-container">
              <img 
                src="/home_imgs/color_of_the_year/Mocha_Mousse.png" 
                alt="Mocha Mousse Color of the Year 2025"
                className="color-image"
              />
              <div className="color-text-overlay">
                <div className="pantone-text">PANTONE</div>
                <div className="color-name">Mocha Mousse</div>
                <div className="color-description">Color of the Year 2025: Thoughtful Indulgence</div>
                <div className="color-box" style={{ backgroundColor: '#9e7863' }}></div>
              </div>
            </div>
            
            <div className="color-bags-section">
              <div className="intro-bag-card">
                <img 
                  src="/boston_bag/1.jpg" 
                  alt="Boston Bag 1"
                  className="intro-bag-image"
                />
                <div className="intro-bag-info">
                  <div className="intro-bag-brand">Coach</div>
                  <div className="intro-bag-name">Leather Shoulder Bag</div>
                  <div className="intro-bag-price">₩120,000</div>
                </div>
              </div>
              
              <div className="intro-bag-card">
                <img 
                  src="/boston_bag/2.jpg" 
                  alt="Boston Bag 2"
                  className="intro-bag-image"
                />
                <div className="intro-bag-info">
                  <div className="intro-bag-brand">Nike</div>
                  <div className="intro-bag-name">Backpack Pro</div>
                  <div className="intro-bag-price">₩89,000</div>
                </div>
              </div>
              
              <div className="intro-bag-card">
                <img 
                  src="/boston_bag/3.jpg" 
                  alt="Boston Bag 3"
                  className="intro-bag-image"
                />
                <div className="intro-bag-info">
                  <div className="intro-bag-brand">Uniqlo</div>
                  <div className="intro-bag-name">Canvas Tote</div>
                  <div className="intro-bag-price">₩29,000</div>
                </div>
              </div>
            </div>
          </div>
          
          {/* Pantone Color 영역 */}
          <div className="pantone-color-section">
            <div className="pantone-color-left">
              {/* 컬러 팔레트 */}
              <div className="pantone-color-palette">
                <div className="pantone-color-item">
                  <div className="pantone-color-swatch" style={{ backgroundColor: '#8da065' }}>
                    <div className="pantone-color-name">Tendril</div>
                  </div>
                </div>
                <div className="pantone-color-item">
                  <div className="pantone-color-swatch" style={{ backgroundColor: '#7b91cc' }}>
                    <div className="pantone-color-name">Cornflower Blue</div>
                  </div>
                </div>
                <div className="pantone-color-item">
                  <div className="pantone-color-swatch" style={{ backgroundColor: '#a492bc' }}>
                    <div className="pantone-color-name">Viola</div>
                  </div>
                </div>
                <div className="pantone-color-item">
                  <div className="pantone-color-swatch" style={{ backgroundColor: '#c99c95' }}>
                    <div className="pantone-color-name">Rose Tan</div>
                  </div>
                </div>
                <div className="pantone-color-item">
                  <div className="pantone-color-swatch" style={{ backgroundColor: '#9d7860' }}>
                    <div className="pantone-color-name">Mocha Mousse</div>
                  </div>
                </div>
              </div>
              
              <div className="pantone-bag-cards">
                <div className="pantone-bag-card">
                  <img 
                    src="/boston_bag/1.jpg" 
                    alt="Boston Bag 1"
                    className="pantone-bag-image"
                  />
                  <div className="pantone-bag-info">
                    <div className="pantone-bag-brand">Coach</div>
                    <div className="pantone-bag-name">Leather Shoulder</div>
                    <div className="pantone-bag-price">₩120,000</div>
                  </div>
                </div>
                
                <div className="pantone-bag-card">
                  <img 
                    src="/boston_bag/2.jpg" 
                    alt="Boston Bag 2"
                    className="pantone-bag-image"
                  />
                  <div className="pantone-bag-info">
                    <div className="pantone-bag-brand">Nike</div>
                    <div className="pantone-bag-name">Sport Waist</div>
                    <div className="pantone-bag-price">₩45,000</div>
                  </div>
                </div>
                
                <div className="pantone-bag-card">
                  <img 
                    src="/boston_bag/3.jpg" 
                    alt="Boston Bag 3"
                    className="pantone-bag-image"
                  />
                  <div className="pantone-bag-info">
                    <div className="pantone-bag-brand">Fossil</div>
                    <div className="pantone-bag-name">Cross Body</div>
                    <div className="pantone-bag-price">₩75,000</div>
                  </div>
                </div>
                
                <div className="pantone-bag-card">
                  <img 
                    src="/boston_bag/4.jpg" 
                    alt="Boston Bag 4"
                    className="pantone-bag-image"
                  />
                  <div className="pantone-bag-info">
                    <div className="pantone-bag-brand">Patagonia</div>
                    <div className="pantone-bag-name">Eco Canvas</div>
                    <div className="pantone-bag-price">₩65,000</div>
                  </div>
                </div>
                
                <div className="pantone-bag-card">
                  <img 
                    src="/boston_bag/5.jpg" 
                    alt="Boston Bag 5"
                    className="pantone-bag-image"
                  />
                  <div className="pantone-bag-info">
                    <div className="pantone-bag-brand">Adidas</div>
                    <div className="pantone-bag-name">Boston Sport</div>
                    <div className="pantone-bag-price">₩85,000</div>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="pantone-color-right">
              <img 
                src="/home_imgs/color_of_the_year/floral.png" 
                alt="Floral Design"
                className="pantone-floral-image"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default IntroductionPage;
