import React, { useRef } from 'react';
import './IntroductionPage.css';

const IntroductionPage: React.FC = () => {
  const galleryRef = useRef<HTMLDivElement>(null);
  
  const celebImages = [
    '/celeb_imgs/celeb_1.jpg',
    '/celeb_imgs/celeb_2.webp',
    '/celeb_imgs/celeb_3.webp',
    '/celeb_imgs/celeb_4.webp',
    '/celeb_imgs/celeb_5.webp'
  ];

  const scrollLeft = () => {
    if (galleryRef.current) {
      galleryRef.current.scrollBy({
        left: -400, // 이미지 하나 너비만큼 이동
        behavior: 'smooth'
      });
    }
  };

  const scrollRight = () => {
    if (galleryRef.current) {
      galleryRef.current.scrollBy({
        left: 400, // 이미지 하나 너비만큼 이동
        behavior: 'smooth'
      });
    }
  };

  return (
    <div className="introduction-page">
      <div className="gallery-container">
        <div className="click-area left" onClick={scrollLeft}></div>
        <div className="celeb-gallery" ref={galleryRef}>
          {celebImages.map((image, index) => (
            <img
              key={index}
              src={image}
              alt={`Celebrity ${index + 1}`}
              className="celeb-image"
            />
          ))}
        </div>
        <div className="click-area right" onClick={scrollRight}></div>
      </div>
    </div>
  );
};

export default IntroductionPage;
