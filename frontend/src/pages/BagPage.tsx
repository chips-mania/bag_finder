import React, { useState, useRef, useEffect } from 'react';
import ImageUpload from '../components/ImageUpload';
import ImagePreview from '../components/ImagePreview';
import type { SessionResponse, BagResult } from '../services/api';
import { apiService } from '../services/api';
import './BagPage.css';

interface BagPageProps {
  session: SessionResponse | null;
  imageUrl: string;
  isLoading: boolean;
  onSessionCreated: (session: SessionResponse, imageUrl: string) => void;
  onError: (errorMessage: string) => void;
  onReset: () => void;
}

const BagPage: React.FC<BagPageProps> = ({
  session,
  imageUrl,
  isLoading,
  onSessionCreated,
  onError,
  onReset
}) => {
  const [showResults, setShowResults] = useState(false);
  const [promptMode, setPromptMode] = useState<'add' | 'remove' | null>('add');
  const [resetSignal, setResetSignal] = useState(0);
  const [previewHeight, setPreviewHeight] = useState<number>(600);
  const [searchResults, setSearchResults] = useState<{ top5: BagResult[], gallery10: BagResult[] } | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [expandedColors, setExpandedColors] = useState<Set<string>>(new Set());
  const colorToggleRefs = useRef<{ [key: string]: HTMLDivElement | null }>({});
  const [minPrice, setMinPrice] = useState(0);
  const [maxPrice, setMaxPrice] = useState(500000);
  const rangeSliderRef = useRef<HTMLDivElement | null>(null);
  
  // 색상 그룹 관련 상태
  const [selectedColorGroups, setSelectedColorGroups] = useState<Set<string>>(new Set());
  
  // 카테고리 관련 상태
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());
  
  // 필터 결과 관련 상태
  const [filterResults, setFilterResults] = useState<any[] | null>(null);
  const [isFilterSearching, setIsFilterSearching] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages] = useState(5); // 총 5페이지
  const [totalItems] = useState(50); // 총 50개 아이템
  
  // 하드코딩된 색상 그룹 데이터
  const COLOR_GROUPS = [
    { id: "1", name: "블랙", color: "#3F3F3F", includedColors: ["블랙"] },
    { id: "2", name: "그레이", color: "#666666", includedColors: ["다크그레이", "중간그레이", "라이트그레이"] },
    { id: "3", name: "화이트", color: "#E3E3E3", includedColors: ["화이트", "아이보리"] },
    { id: "4", name: "블루", color: "#2320fc", includedColors: ["블루", "다크블루", "네이비", "다크네이비", "스카이블루"] },
    { id: "5", name: "그린", color: "#2bac15", includedColors: ["그린", "라이트그린", "다크그린", "올리브그린", "카키", "민트", "라임"] },
    { id: "6", name: "레드", color: "#991515", includedColors: ["레드", "딥레드", "버건디", "브릭"] },
    { id: "7", name: "베이지", color: "#9f8c76", includedColors: ["카멜", "다크베이지", "베이지", "오트밀"] },
    { id: "8", name: "브라운", color: "#5c4033", includedColors: ["브라운", "다크브라운", "라이트브라운"] },
    { id: "9", name: "핑크", color: "#ff69b4", includedColors: ["핑크", "다크핑크", "라이트핑크", "로즈골드"] },
    { id: "10", name: "오렌지", color: "#ff7f00", includedColors: ["오렌지", "라이트오렌지", "머스타드", "피치"] },
    { id: "11", name: "옐로우", color: "#fbea2a", includedColors: ["옐로우", "라이트옐로우"] },
    { id: "12", name: "퍼플", color: "#880ed4", includedColors: ["퍼플", "라벤더"] }
  ];

  // 하단 갤러리 스크롤 제어
  const bottomGalleryRef = useRef<HTMLDivElement | null>(null);
  const resultsListRef = useRef<HTMLDivElement | null>(null);
  const scrollBottomGallery = (direction: 'left' | 'right') => {
    const el = bottomGalleryRef.current;
    if (!el) return;
    const delta = direction === 'left' ? -el.clientWidth * 0.8 : el.clientWidth * 0.8;
    el.scrollBy({ left: delta, behavior: 'smooth' });
  };
  const scrollResults = (direction: 'up' | 'down') => {
    const el = resultsListRef.current;
    if (!el) return;
    const delta = direction === 'up' ? -el.clientHeight * 0.8 : el.clientHeight * 0.8;
    el.scrollBy({ top: delta, behavior: 'smooth' });
  };

  // 색상 파싱 함수
  const parseColors = (colorString: string | null): string[] => {
    if (!colorString) return [];
    try {
      // JSON 배열 형태로 파싱 시도
      const parsed = JSON.parse(colorString);
      if (Array.isArray(parsed)) {
        // 배열의 각 요소에서 따옴표와 대괄호 제거
        return parsed.map(color => color.trim().replace(/['"\[\]]/g, '')).filter(c => c);
      }
      return [colorString.trim().replace(/['"\[\]]/g, '')];
    } catch {
      // JSON이 아닌 경우 쉼표로 분리
      return colorString.split(',').map(c => c.trim().replace(/['"\[\]]/g, '')).filter(c => c);
    }
  };

  // 외부 클릭 감지
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Element;
      
      // 모든 color toggle container를 확인
      Object.keys(colorToggleRefs.current).forEach(bagId => {
        const container = colorToggleRefs.current[bagId];
        if (container && !container.contains(target)) {
          setExpandedColors(prev => {
            const newSet = new Set(prev);
            newSet.delete(bagId);
            return newSet;
          });
        }
      });
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // 가격 범위 시각화 업데이트
  useEffect(() => {
    if (rangeSliderRef.current) {
      const minPercent = (minPrice / 500000) * 100;
      const maxPercent = (maxPrice / 500000) * 100;
      
      rangeSliderRef.current.style.setProperty('--min-percent', `${minPercent}%`);
      rangeSliderRef.current.style.setProperty('--max-percent', `${maxPercent}%`);
    }
  }, [minPrice, maxPrice]);

  // 필터 검색 함수
  const handleFilterSearch = async () => {
    setIsFilterSearching(true);
    try {
      // 50개 아이템 생성 (시뮬레이션)
      const mockItems = Array.from({ length: 50 }, (_, index) => ({
        id: `item-${index + 1}`,
        name: `가방 ${index + 1}`,
        brand: `브랜드 ${Math.floor(index / 10) + 1}`,
        price: Math.floor(Math.random() * 500000) + 50000,
        colors: ['블랙', '브라운', '네이비', '레드', '그린'].slice(0, Math.floor(Math.random() * 5) + 1),
        similarity: Math.random() * 0.3 + 0.7 // 0.7 ~ 1.0
      }));
      
      setFilterResults(mockItems);
    } catch (error) {
      console.error('Filter search error:', error);
    } finally {
      setIsFilterSearching(false);
    }
  };

  // 페이지 변경 함수
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  // 현재 페이지의 아이템들 가져오기
  const getCurrentPageItems = () => {
    if (!filterResults) return [];
    const startIndex = (currentPage - 1) * 10;
    const endIndex = startIndex + 10;
    return filterResults.slice(startIndex, endIndex);
  };

  // 색상 토글 함수
  const toggleColorExpansion = (bagId: string) => {
    setExpandedColors(prev => {
      const newSet = new Set(prev);
      if (newSet.has(bagId)) {
        newSet.delete(bagId);
      } else {
        newSet.add(bagId);
      }
      return newSet;
    });
  };

  // 색상 그룹 토글 함수
  const toggleColorGroup = (groupId: string) => {
    setSelectedColorGroups(prev => {
      const newSet = new Set(prev);
      if (newSet.has(groupId)) {
        newSet.delete(groupId);
      } else {
        newSet.add(groupId);
      }
      return newSet;
    });
  };

  // 카테고리 토글 함수
  const toggleCategory = (category: string) => {
    setSelectedCategories(prev => {
      const newSet = new Set(prev);
      if (newSet.has(category)) {
        newSet.delete(category);
      } else {
        newSet.add(category);
      }
      return newSet;
    });
  };

  // 색상명을 색상코드로 변환
  const getColorCode = (colorName: string): string => {
    // 여기에 색상명과 색상코드 dict를 입력하세요
    const colorMap: { [key: string]: string } = {
      "블랙": "#000000",
      "그레이": "#999999",
      "블루": "#2320fc",
      "그린": "#2bac15",
      "네이비": "#0c0c69",
      "브라운": "#964b00",
      "아이보리": "#fcfcf2",
      "핑크": "#ff69b4",
      "레드": "#ff0000",
      "베이지": "#e7d7a7",
      "카키": "#5b5a3a",
      "오렌지": "#ff7f00",
      "옐로우": "#fbea2a",
      "다크그린": "#1d4221",
      "다크그레이": "#53565b",
      "화이트": "#ffffff",
      "퍼플": "#880ed4",
      "민트": "#40c1ab",
      "버건디": "#660033",
      "카멜": "#d89f3b",
      "라임": "#d0fe1d",
      "스카이블루": "#5bc1e7",
      "다크네이비": "#1e3250",
      "다크브라운": "#5c4033",
      "다크블루": "#092ca6",
      "다크베이지": "#9f8c76",
      "라이트그린": "#90EE90"
    };
    
    const normalizedColor = colorName.trim().replace(/['"\[\]]/g, '');
    return colorMap[normalizedColor] || '#CCCCCC'; // 기본값은 회색
  };

  // 검색 핸들러
  const handleSearch = async () => {
    if (!session) return;
    
    setIsSearching(true);
    try {
      // 선택된 색상 그룹들의 포함 색상들을 수집
      const selectedColors: string[] = [];
      selectedColorGroups.forEach(groupId => {
        const group = COLOR_GROUPS.find(g => g.id === groupId);
        if (group) {
          selectedColors.push(...group.includedColors);
        }
      });
      
      // 선택된 색상이 없으면 빈 배열로 전송 (모든 색상 포함)
      const results = await apiService.searchBags(session.session_id, selectedColors);
      setSearchResults(results);
      setShowResults(true);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      const message = typeof detail === 'string' ? detail : '검색 중 오류가 발생했습니다.';
      onError(message);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="bag-page">
      <div className="bag-header">
      </div>

      <main className={`bag-main ${showResults ? 'preview-mode' : 'upload-mode'}`}>
        <div className="bag-content">
          <div className="upload-section">
            {!session ? (
              <ImageUpload
                onSessionCreated={onSessionCreated}
                onError={onError}
                isLoading={isLoading}
              />
            ) : (
              <ImagePreview
                session={session}
                imageUrl={imageUrl}
                onError={onError}
                promptMode={promptMode}
                resetSignal={resetSignal}
                onHeightChange={(h) => setPreviewHeight(h)}
              />
            )}

            {session && (
              <div className="action-buttons">
                <button 
                  className="search-button"
                  onClick={handleSearch}
                  disabled={isSearching}
                >
                  {isSearching ? 'SEARCHING...' : 'SEARCH'}
                </button>
                <button 
                  className="reset-button"
                  onClick={() => {
                    onReset();
                    setShowResults(false);
                    setSearchResults(null);
                    setPromptMode(null);
                  }}
                >
                  NEW IMAGE
                </button>
              </div>
            )}

            {session && (
              <div className="prompt-buttons">
                <button 
                  className={`prompt-button add-button ${promptMode === 'add' ? 'active' : ''}`}
                  onClick={() => setPromptMode('add')}
                >
                  ADD
                </button>
                <button 
                  className={`prompt-button remove-button ${promptMode === 'remove' ? 'active' : ''}`}
                  onClick={() => setPromptMode('remove')}
                >
                  REMOVE
                </button>
                <button 
                  className="prompt-button reset-prompt-button"
                  onClick={() => {
                    setResetSignal((v) => v + 1);
                    setPromptMode('add');
                  }}
                >
                  RESET
                </button>
              </div>
            )}
          </div>

          {showResults && searchResults && (
            <div className="results-section" style={{ height: `calc(${previewHeight + 90}px - 75px)` }}>
              <div className="results-header">
                <h3>유사도 BEST</h3>
              </div>
              <div className="results-list" ref={resultsListRef}>
                {searchResults.top5.map((bag) => (
                  <div 
                    className="bag-card" 
                    key={bag.bag_id}
                  >
                    <img 
                      src={bag.thumbnail || ''} 
                      alt={bag.bag_name || 'Bag'} 
                      onClick={() => bag.link && window.open(bag.link, '_blank')}
                      style={{ cursor: bag.link ? 'pointer' : 'default' }}
                    />
                    <div className="bag-info">
                      <div className="bag-info-row">
                        <span className="bag-name">{bag.bag_name || 'Unknown'}</span>
                        <span className="separator">|</span>
                        <span className="bag-brand">{bag.brand || 'Unknown'}</span>
                      </div>
                      <div className="bag-info-row">
                        <span className="bag-price">{bag.price ? bag.price.toLocaleString() : 'N/A'}</span>
                        <span className="separator">|</span>
                        <span className="bag-type">{bag.category || 'N/A'}</span>
                        <span className="separator">|</span>
                        <span className="bag-material">{bag.material || 'N/A'}</span>
                        <span className="separator">|</span>
                        <div className="color-circles">
                          {parseColors(bag.color).length > 6 ? (
                            <div 
                              className="color-toggle-container"
                              ref={(el) => {
                                if (el) {
                                  colorToggleRefs.current[bag.bag_id] = el;
                                }
                              }}
                            >
                              <button 
                                className="color-toggle-btn"
                                onClick={() => toggleColorExpansion(bag.bag_id)}
                              >
                                상세색상보기
                              </button>
                              {expandedColors.has(bag.bag_id) && (
                                <div className="color-popup">
                                  <div className="color-popup-content">
                                    {parseColors(bag.color).map((color, index) => {
                                      const colorCode = getColorCode(color);
                                      const isWhite = colorCode.toLowerCase() === '#ffffff' || colorCode.toLowerCase() === '#fff';
                                      return (
                                        <div
                                          key={index}
                                          className="color-circle"
                                          style={{ 
                                            backgroundColor: colorCode,
                                            border: isWhite ? '1px solid rgb(157, 157, 157)' : '1px solid #ffffff'
                                          }}
                                          title={color}
                                        />
                                      );
                                    })}
                                  </div>
                                </div>
                              )}
                            </div>
                          ) : (
                            parseColors(bag.color).map((color, index) => {
                              const colorCode = getColorCode(color);
                              const isWhite = colorCode.toLowerCase() === '#ffffff' || colorCode.toLowerCase() === '#fff';
                              return (
                                <div
                                  key={index}
                                  className="color-circle"
                                  style={{ 
                                    backgroundColor: colorCode,
                                    border: isWhite ? '1px solid rgb(157, 157, 157)' : '1px solid #ffffff'
                                  }}
                                  title={color}
                                />
                              );
                            })
                          )}
                        </div>
                        <span className="separator">|</span>
                        <span className="similarity-badge" title={`유사도: ${(bag.similarity * 100).toFixed(1)}%`}>
                          {(bag.similarity * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <button
                className="results-arrow up"
                type="button"
                onClick={() => scrollResults('up')}
                aria-label="scroll up"
              />
              <button
                className="results-arrow down"
                type="button"
                onClick={() => scrollResults('down')}
                aria-label="scroll down"
              />
            </div>
          )}

          {showResults && searchResults && (
            <div className="summary-section">
              <div className="gallery-header">
                <h3>추천 가방</h3>
              </div>
              <div className="bottom-gallery" ref={bottomGalleryRef}>
                <div className="gallery-track">
                  {searchResults.gallery10.map((bag) => (
                    <div 
                      className="gallery-item" 
                      key={bag.bag_id}
                      onClick={() => bag.link && window.open(bag.link, '_blank')}
                      style={{ cursor: bag.link ? 'pointer' : 'default' }}
                      title={`${bag.bag_name || 'Unknown'} - ${(bag.similarity * 100).toFixed(1)}%`}
                    >
                      <div className="gallery-image-container">
                        <img src={bag.thumbnail || ''} alt={bag.bag_name || 'Bag'} />
                        <div className="gallery-similarity-badge">
                          {(bag.similarity * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div className="gallery-item-info">
                        <div className="gallery-brand">{bag.brand || 'Unknown'}</div>
                        <div className="gallery-name">{bag.bag_name || 'Unknown'}</div>
                        <div className="gallery-price">{bag.price ? bag.price.toLocaleString() : 'N/A'}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <button 
                className="gallery-arrow left" 
                type="button" 
                onClick={() => scrollBottomGallery('left')} 
                aria-label="scroll left" 
              />
              <button 
                className="gallery-arrow right" 
                type="button" 
                onClick={() => scrollBottomGallery('right')} 
                aria-label="scroll right" 
              />
            </div>
          )}
        </div>
        
        {/* 필터 검색 섹션 - SEARCH 버튼을 누른 후에만 표시 */}
        {showResults && (
        <div className="filter-search-section">
          <div className="filter-settings">
            <h3>FILTER</h3>
            
            {/* 검색 영역 */}
            <div className="search-area">
              <input 
                type="text" 
                placeholder="검색어를 입력하세요" 
                className="search-input"
              />
            </div>
            
            {/* 필터 컨테이너 */}
            <div className="filter-container">
              {/* 필터 영역 */}
              <div className="filters-area">
                <div className="filter-group">
                  <label>Category</label>
                  <div className="category-container">
                    {/* 위 그리드: 2행 3열 */}
                    <div className="toggle-group category-grid-top">
                      <button 
                        className={`toggle-button ${selectedCategories.has('숄더백') ? 'active' : ''}`}
                        onClick={() => toggleCategory('숄더백')}
                      >
                        숄더백
                      </button>
                      <button 
                        className={`toggle-button ${selectedCategories.has('토트백') ? 'active' : ''}`}
                        onClick={() => toggleCategory('토트백')}
                      >
                        토트백
                      </button>
                      <button 
                        className={`toggle-button ${selectedCategories.has('크로스백') ? 'active' : ''}`}
                        onClick={() => toggleCategory('크로스백')}
                      >
                        크로스백
                      </button>
                      <button 
                        className={`toggle-button ${selectedCategories.has('보스턴백') ? 'active' : ''}`}
                        onClick={() => toggleCategory('보스턴백')}
                      >
                        보스턴백
                      </button>
                      <button 
                        className={`toggle-button ${selectedCategories.has('클러치') ? 'active' : ''}`}
                        onClick={() => toggleCategory('클러치')}
                      >
                        클러치
                      </button>
                      <button 
                        className={`toggle-button ${selectedCategories.has('백팩') ? 'active' : ''}`}
                        onClick={() => toggleCategory('백팩')}
                      >
                        백팩
                      </button>
                    </div>
                    
                    {/* 아래 그리드: 1행 2열 */}
                    <div className="toggle-group category-grid-bottom">
                      <button 
                        className={`toggle-button ${selectedCategories.has('에코/캔버스백') ? 'active' : ''}`}
                        onClick={() => toggleCategory('에코/캔버스백')}
                      >
                        에코/캔버스백
                      </button>
                      <button 
                        className={`toggle-button ${selectedCategories.has('웨이스트백') ? 'active' : ''}`}
                        onClick={() => toggleCategory('웨이스트백')}
                      >
                        웨이스트백
                      </button>
                    </div>
                  </div>
                </div>
                
                <div className="filter-group">
                  <label>Color</label>
                  <div className="toggle-group">
                    {COLOR_GROUPS.map((group) => (
                      <button
                        key={group.id}
                        className={`toggle-button color-group-button ${selectedColorGroups.has(group.id) ? 'active' : ''}`}
                        onClick={() => toggleColorGroup(group.id)}
                        title={group.includedColors.join(', ')}
                      >
                        <div className="color-circle" style={{
                          backgroundColor: selectedColorGroups.has(group.id) ? group.color : 'transparent',
                          border: `1px solid ${group.color}`
                        }}></div>
                        <span className="color-name">{group.name}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              
              {/* 가격대 영역 */}
              <div className="price-filter-area">
                <div className="filter-group">
                  <label>Price Range</label>
                  <div className="price-range">
                    <div className="range-slider" ref={rangeSliderRef}>
                      <input 
                        type="range" 
                        min="0" 
                        max="500000" 
                        step="10000" 
                        value={minPrice}
                        onChange={(e) => {
                          const value = parseInt(e.target.value);
                          if (value < maxPrice) {
                            setMinPrice(value);
                          }
                        }}
                        className="range-input min-range" 
                      />
                      <input 
                        type="range" 
                        min="0" 
                        max="500000" 
                        step="10000" 
                        value={maxPrice}
                        onChange={(e) => {
                          const value = parseInt(e.target.value);
                          if (value > minPrice) {
                            setMaxPrice(value);
                          }
                        }}
                        className="range-input max-range" 
                      />
                      
                      {/* 최소값 팝업 */}
                      <div 
                        className="price-popup min-popup"
                        style={{
                          left: `calc(${(minPrice / 500000) * 100}% + 10px)`
                        }}
                      >
                        {minPrice.toLocaleString()}원
                      </div>
                      
                      {/* 최대값 팝업 */}
                      <div 
                        className="price-popup max-popup"
                        style={{
                          left: `${(maxPrice / 500000) * 100}%`
                        }}
                      >
                        {maxPrice.toLocaleString()}원
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            {/* 버튼 영역 */}
            <div className="filter-buttons">
              <button
                className="filter-search-button"
                onClick={handleFilterSearch}
                disabled={isFilterSearching}
              >
                {isFilterSearching ? 'SEARCHING...' : 'SEARCH'}
              </button>
              <button 
                className="filter-reset-button"
                onClick={() => {
                  setSelectedCategories(new Set());
                  setSelectedColorGroups(new Set());
                  setMinPrice(0);
                  setMaxPrice(500000);
                }}
              >
                RESET
              </button>
            </div>
          </div>
            <div className="filter-results">
              <h3>RESULTS</h3>
              <div className="filter-results-content">
                {isFilterSearching ? (
                  <div className="loading-message">검색 중...</div>
                ) : filterResults ? (
                  <>
                    {/* 2행 5열 그리드 - 현재 페이지 아이템들 */}
                    <div className="bag-grid">
                      {getCurrentPageItems().map((item, index) => (
                        <div key={item.id} className="bag-card">
                          <div className="bag-image-container">
                            <div className="empty-image-placeholder">
                              <span>이미지</span>
                            </div>
                            <div className="similarity-overlay">
                              {(item.similarity * 100).toFixed(1)}%
                            </div>
                          </div>
                          <div className="bag-info">
                            <div className="bag-name">{item.name}</div>
                            <div className="bag-brand">{item.brand}</div>
                            <div className="bag-price">₩{item.price.toLocaleString()}</div>
                            <div className="bag-colors">
                              {item.colors.map((color, colorIndex) => (
                                <span key={colorIndex} className="color-tag">{color}</span>
                              ))}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* 페이지네이션 */}
                    <div className="pagination">
                      <button
                        className="page-arrow"
                        onClick={() => handlePageChange(Math.max(1, currentPage - 1))}
                        disabled={currentPage === 1}
                      >
                        ←
                      </button>
                      
                      <div className="page-numbers">
                        {Array.from({ length: totalPages }, (_, i) => {
                          const pageNum = i + 1;
                          return (
                            <button
                              key={pageNum}
                              className={`page-number ${currentPage === pageNum ? 'active' : ''}`}
                              onClick={() => handlePageChange(pageNum)}
                            >
                              {pageNum}
                            </button>
                          );
                        })}
                      </div>
                      
                      <button
                        className="page-arrow"
                        onClick={() => handlePageChange(Math.min(totalPages, currentPage + 1))}
                        disabled={currentPage === totalPages}
                      >
                        →
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="no-results">검색 결과가 없습니다.</div>
                )}
              </div>
            </div>
        </div>
        )}
      </main>
    </div>
  );
};

export default BagPage;
