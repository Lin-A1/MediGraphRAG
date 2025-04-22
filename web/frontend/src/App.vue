<script setup>
import { ref, onMounted, reactive, nextTick } from 'vue';
import * as echarts from 'echarts';
import neo4j from 'neo4j-driver';

// 定义响应式数据
const keyword = ref('');
const loading = ref(false);
const error = ref('');
const knowledgeData = ref(null);
const selectedAnswer = ref('');
const showAnswer = ref(false);
const graphLoading = ref(false);
const graphError = ref('');
const graphData = ref(null);
const graphChart = ref(null);
const graphContainer = ref(null);

// Neo4j连接配置
const neovisConfig = {
  container_id: "neovis-graph",
  server_url: "bolt://localhost:7687",
  server_user: "neo4j",
  server_password: "password", // 请替换为您的实际密码
  labels: {
    "知识点": {
      caption: "name",
      size: "pagerank",
      community: "community",
      title_properties: ["name", "description"],
      color: "#1976d2"
    },
    "疾病": {
      caption: "name",
      size: "pagerank",
      community: "community",
      title_properties: ["name", "description"],
      color: "#ef4444"
    },
    "症状": {
      caption: "name",
      size: "pagerank",
      community: "community",
      title_properties: ["name", "description"],
      color: "#22c55e"
    },
    "药物": {
      caption: "name",
      size: "pagerank",
      community: "community",
      title_properties: ["name", "description"],
      color: "#f59e0b"
    },
  },
  relationships: {
    "相关": {
      caption: true,
      thickness: "weight",
      title_properties: ["type", "weight"],
      color: "#64748b"
    },
    "引起": {
      caption: true,
      thickness: "weight",
      title_properties: ["type", "weight"],
      color: "#ef4444"
    },
    "治疗": {
      caption: true,
      thickness: "weight",
      title_properties: ["type", "weight"],
      color: "#22c55e"
    },
  },
  initial_cypher: "MATCH (n) RETURN n LIMIT 10",
  arrows: true,
  hierarchical: false,
  physics: {
    stabilization: {
      enabled: true,
      iterations: 1000,
      updateInterval: 25,
      onlyDynamicEdges: false,
      fit: true
    },
    barnesHut: {
      gravitationalConstant: -2000,
      centralGravity: 0.3,
      springLength: 200,
      springConstant: 0.04,
      damping: 0.09,
      avoidOverlap: 0.1
    }
  },
  visConfig: {
    nodes: {
      shape: "dot",
      font: {
        size: 12,
        face: "Noto Sans SC"
      },
      borderWidth: 1,
      shadow: true
    },
    edges: {
      font: {
        size: 10,
        face: "Noto Sans SC"
      },
      smooth: {
        type: "continuous"
      },
      arrows: {
        to: { enabled: true, scaleFactor: 0.5 }
      }
    },
    interaction: {
      hover: true,
      tooltipDelay: 200,
      hideEdgesOnDrag: true,
      navigationButtons: true
    }
  }
};

// 加载状态和进度相关
const loadingStates = reactive({
  progress: 0,
  status: '',
  steps: [
    { text: '正在检索医学知识库...', progress: 20 },
    { text: '正在清洗知识点内容...', progress: 40 },
    { text: '正在关联相关信息...', progress: 60 },
    { text: '正在生成医学试题...', progress: 80 },
    { text: '即将完成...', progress: 95 }
  ],
  currentStep: 0,
  timer: null,
  abortController: null
});

// 显示加载提示
const loadingTips = [
  '医学知识检索需要一点时间，请耐心等待...',
  '正在为您精心筛选最相关的医学知识',
  '大模型正在思考中，马上就好',
  '试题生成涉及多个步骤，可能需要几秒钟',
  '我们正在确保信息的准确性和质量'
];
const currentTip = ref(loadingTips[0]);
const tipTimer = ref(null);

// API 基础URL
const API_BASE_URL = 'http://localhost:8000';

// 图表配置
const graphOptions = {
  title: {
    text: '知识图谱',
    left: 'center'
  },
  tooltip: {
    trigger: 'item',
    formatter: function (params) {
      if (params.dataType === 'node') {
        return `${params.data.name}`;
      }
      return `${params.data.source} ${params.data.label || '关联'} ${params.data.target}`;
    }
  },
  series: [{
    type: 'graph',
    layout: 'force',
    data: [],
    links: [],
    force: {
      repulsion: 2000,  // 增加节点之间的斥力
      edgeLength: [100, 300],  // 增加边的长度范围
      gravity: 0.05,  // 减小重力，让节点分布更开
      layoutAnimation: true  // 启用布局动画
    },
    zoom: 0.8,  // 默认缩小一点以显示更多内容
    roam: true,  // 允许缩放和平移
    nodeScaleRatio: 0.6,  // 防止节点太大
    draggable: true,  // 允许拖拽节点
    layout: 'force',
    emphasis: {
      focus: 'adjacency'  // 突出显示相邻节点
    },
    roam: true,
    label: {
      show: true,
      position: 'right',
      formatter: function(params) {
        const name = params.data.name;
        // 如果名称长度超过8个字符，显示前8个字符加省略号
        return name.length > 8 ? name.substring(0, 8) + '...' : name;
      },
      fontSize: 12,
      color: '#333',
      backgroundColor: 'rgba(255, 255, 255, 0.8)',
      padding: [2, 4],
      borderRadius: 2
    },
    force: {
      repulsion: 1000,
      edgeLength: [50, 200],
      gravity: 0.1
    },
    emphasis: {
      focus: 'adjacency',
      lineStyle: {
        width: 4
      },
      label: {
        show: true,
        formatter: function(params) {
          // 鼠标悬停时显示完整名称
          return params.data.name;
        },
        fontSize: 14,
        fontWeight: 'bold',
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        padding: [4, 8],
        borderRadius: 4
      }
    },
    lineStyle: {
      color: '#64748b',
      curveness: 0.3,
      width: 2
    },
    itemStyle: {
      borderWidth: 2,
      borderColor: '#fff',
      shadowBlur: 10,
      shadowColor: 'rgba(0, 0, 0, 0.3)'
    }
  }]
};

// 初始化图表
const initGraph = () => {
  if (!graphContainer.value) {
    console.error("图谱容器未找到");
    return;
  }

  try {
    console.log("开始初始化图表...");
    if (graphChart.value) {
      graphChart.value.dispose();
    }
    
    // 确保容器有尺寸
    graphContainer.value.style.width = '100%';
    graphContainer.value.style.height = '500px';
    
    graphChart.value = echarts.init(graphContainer.value);
    console.log("ECharts实例创建成功");
    
    // 设置初始空数据
    graphChart.value.setOption({
      ...graphOptions,
      series: [{
        ...graphOptions.series[0],
        data: [],
        links: []
      }]
    });
    
    // 自适应大小
    window.addEventListener('resize', () => {
      graphChart.value?.resize();
    });
    
    console.log("图表初始化成功");
  } catch (err) {
    console.error("图表初始化失败:", err);
    graphError.value = "图表初始化失败: " + err.message;
  }
};

// 更新图表数据
const updateGraphData = (nodes, links) => {
  if (!graphChart.value) {
    console.error("图表实例未找到");
    return;
  }
  
  console.log("更新图表数据:", { nodes, links });
  
  const option = {
    series: [{
      type: 'graph',
      layout: 'force',
      data: nodes.map(node => ({
        name: node.name,
        value: node.value,
        category: node.category,
        symbolSize: node.isBaseNode ? 60 : 40,
        itemStyle: {
          color: '#1976d2', // 统一使用蓝色
          opacity: node.isBaseNode ? 1 : 0.6
        }
      })),
      links: links.map(link => ({
        source: link.source,
        target: link.target,
        label: {
          show: true,
          formatter: function(params) {
            const label = params.data.label;
            // 如果label是对象，则显示其type属性
            if (typeof label === 'object' && label !== null) {
              return label.type || '关联';
            }
            // 如果label是字符串，直接显示
            return label || '关联';
          },
          fontSize: 12,
          color: '#64748b',
          backgroundColor: 'rgba(255, 255, 255, 0.8)',
          padding: [4, 8],
          borderRadius: 4,
          position: 'middle'
        },
        lineStyle: {
          width: 2,
          curveness: 0.3,
          color: '#64748b'
        }
      })),
      categories: [
        { name: '知识点' },
        { name: '疾病' },
        { name: '症状' },
        { name: '药物' }
      ],
      roam: true,
      label: {
        show: true,
        position: 'right',
        formatter: function(params) {
          const name = params.data.name;
          return name.length > 8 ? name.substring(0, 8) + '...' : name;
        },
        fontSize: 12,
        color: '#333',
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
        padding: [2, 4],
        borderRadius: 2
      },
      force: {
        repulsion: 1000,
        edgeLength: [50, 200],
        gravity: 0.1
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: {
          width: 4
        },
        label: {
          show: true,
          formatter: function(params) {
            return params.data.name;
          },
          fontSize: 14,
          fontWeight: 'bold',
          backgroundColor: 'rgba(255, 255, 255, 0.9)',
          padding: [4, 8],
          borderRadius: 4
        }
      },
      lineStyle: {
        color: '#64748b',
        curveness: 0.3,
        width: 2
      },
      itemStyle: {
        borderWidth: 2,
        borderColor: '#fff',
        shadowBlur: 10,
        shadowColor: 'rgba(0, 0, 0, 0.3)'
      }
    }]
  };
  
  console.log("设置图表选项:", option);
  graphChart.value.setOption(option, true);
};

// 搜索关键词相关的知识图谱
const searchGraphByKeyword = async (query) => {
  if (!query) return;
  
  graphLoading.value = true;
  graphError.value = '';
  
  try {
    console.log("开始搜索图谱:", query);
    const response = await fetch(`${API_BASE_URL}/graph/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ keyword: query })
    });
    
    if (!response.ok) {
      throw new Error('获取图谱数据失败');
    }
    
    const data = await response.json();
    console.log("获取到图谱数据:", data);
    
    // 更新图谱数据，保留现有数据
    if (!graphData.value) {
      graphData.value = { query, timestamp: Date.now() };
    } else {
      graphData.value.query = graphData.value.query + '、' + query;
    }
    
    // 更新图表数据，合并新数据
    const existingNodes = graphChart.value?.getOption()?.series[0]?.data || [];
    const existingLinks = graphChart.value?.getOption()?.series[0]?.links || [];
    
    const newNodes = data.nodes.filter(node => 
      !existingNodes.some(existingNode => existingNode.name === node.name)
    );
    const newLinks = data.links.filter(link => 
      !existingLinks.some(existingLink => 
        existingLink.source === link.source && 
        existingLink.target === link.target
      )
    );
    
    updateGraphData([...existingNodes, ...newNodes], [...existingLinks, ...newLinks]);
    
  } catch (err) {
    console.error("图谱查询失败:", err);
    graphError.value = "图谱数据查询失败: " + err.message;
  } finally {
    graphLoading.value = false;
  }
};

// 模拟进度更新
const startProgressSimulation = () => {
  if (loadingStates.timer) {
    clearInterval(loadingStates.timer);
  }
  
  loadingStates.progress = 0;
  loadingStates.currentStep = 0;
  loadingStates.status = loadingStates.steps[0].text;
  
  // 启动提示轮换
  if (tipTimer.value) clearInterval(tipTimer.value);
  currentTip.value = loadingTips[0];
  let tipIndex = 1;
  tipTimer.value = setInterval(() => {
    currentTip.value = loadingTips[tipIndex % loadingTips.length];
    tipIndex++;
  }, 5000);
  
  // 模拟进度
  loadingStates.timer = setInterval(() => {
    if (loadingStates.currentStep < loadingStates.steps.length - 1 &&
        loadingStates.progress >= loadingStates.steps[loadingStates.currentStep].progress) {
      loadingStates.currentStep++;
      loadingStates.status = loadingStates.steps[loadingStates.currentStep].text;
    }
    
    // 进度增加速度随着进度增大而降低
    const increment = Math.max(0.5, (100 - loadingStates.progress) / 40);
    loadingStates.progress = Math.min(95, loadingStates.progress + increment);

    // 如果加载完成，清除定时器
    if (!loading.value) {
      clearInterval(loadingStates.timer);
      clearInterval(tipTimer.value);
      loadingStates.progress = 100;
      loadingStates.status = '加载完成';
    }
  }, 800);
};

// 取消请求
const cancelRequest = () => {
  if (loadingStates.abortController) {
    loadingStates.abortController.abort();
  }
  
  // 清理所有计时器
  if (loadingStates.timer) {
    clearInterval(loadingStates.timer);
    loadingStates.timer = null;
  }
  
  if (tipTimer.value) {
    clearInterval(tipTimer.value);
    tipTimer.value = null;
  }
  
  loading.value = false;
  error.value = '请求已取消';
  loadingStates.progress = 0;
};

// 获取知识点和试题
const fetchKnowledgeAndQuestion = async () => {
  if (!keyword.value.trim()) {
    error.value = '请输入搜索关键词';
    return;
  }

  try {
    // 取消之前的请求
    if (loadingStates.abortController) {
      loadingStates.abortController.abort();
    }
    
    loadingStates.abortController = new AbortController();
    loading.value = true;
    error.value = '';
    showAnswer.value = false;
    selectedAnswer.value = '';
    knowledgeData.value = null;
    
    // 清空知识图谱
    graphData.value = null;
    if (graphChart.value) {
      graphChart.value.setOption({
        ...graphOptions,
        series: [{
          ...graphOptions.series[0],
          data: [],
          links: []
        }]
      });
    }
    
    // 启动进度条模拟
    startProgressSimulation();
    
    const response = await fetch(`${API_BASE_URL}/get-knowledge-and-question`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ keyword: keyword.value }),
      signal: loadingStates.abortController.signal
    });

    if (!response.ok) {
      throw new Error('请求失败');
    }

    const data = await response.json();
    knowledgeData.value = data;
    
    // 完成进度
    loadingStates.progress = 100;
    loadingStates.status = '加载完成';
    
    // 使用所有相关词搜索图谱
    if (data.related_keywords && data.related_keywords.length > 0) {
      await nextTick();
      // 使用所有相关词
      for (const relatedKeyword of data.related_keywords) {
        await searchGraphByKeyword(relatedKeyword);
      }
    }
    
  } catch (err) {
    if (err.name === 'AbortError') {
      console.log('请求已取消');
    } else {
      error.value = '获取数据失败，请重试';
      console.error('Error:', err);
    }
  } finally {
    loading.value = false;
    
    // 清理计时器
    if (loadingStates.timer) {
      clearInterval(loadingStates.timer);
      loadingStates.timer = null;
    }
    
    if (tipTimer.value) {
      clearInterval(tipTimer.value);
      tipTimer.value = null;
    }
  }
};

// 检查答案
const checkAnswer = (key) => {
  selectedAnswer.value = key;
  showAnswer.value = true;
};

// 检查健康状态
const checkHealth = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    const data = await response.json();
    console.log('API健康状态:', data);
  } catch (err) {
    console.error('API健康检查失败:', err);
  }
};

// 组件挂载时检查API健康状态
onMounted(() => {
  checkHealth();
  nextTick(() => {
    initGraph();
  });
});
</script>

<template>
  <div class="app-container">
    <div class="app-header">
      <div class="logo">医学知识系统</div>
    </div>
    
    <div class="main-content">
      <!-- 搜索区域 -->
      <div class="search-section">
        <div class="search-wrapper">
          <div class="search-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
          </div>
          <input 
            type="text" 
            v-model="keyword" 
            placeholder="输入医学关键词进行搜索..." 
            class="search-input"
            @keyup.enter="fetchKnowledgeAndQuestion"
            :disabled="loading"
          >
          <button v-if="!loading" 
            class="search-button" 
            @click="fetchKnowledgeAndQuestion"
          >
            <span>搜索</span>
          </button>
          <button v-else
            class="search-button cancel-button" 
            @click="cancelRequest"
          >
            <span>取消</span>
          </button>
        </div>
        <div v-if="error" class="error-message">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          {{ error }}
        </div>
      </div>

      <!-- 加载进度条 -->
      <div v-if="loading" class="progress-container">
        <div class="progress-status">
          <div class="status-text">{{ loadingStates.status }}</div>
          <div class="progress-percentage">{{ Math.round(loadingStates.progress) }}%</div>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: `${loadingStates.progress}%` }"></div>
        </div>
        <div class="progress-tip">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="16" x2="12" y2="12"></line>
            <line x1="12" y1="8" x2="12.01" y2="8"></line>
          </svg>
          <span>{{ currentTip }}</span>
        </div>
      </div>

      <div class="content-section">
        <!-- 左侧区域 -->
        <div class="left-section">
          <!-- 知识点区域 -->
          <div class="card knowledge-section">
            <div class="card-header">
              <div class="card-title">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
                  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
                </svg>
                <span>知识点</span>
              </div>
              <div class="related-keywords" v-if="knowledgeData?.related_keywords?.length">
                相关词：{{ knowledgeData.related_keywords.join('、') }}
              </div>
            </div>
            <div class="card-content custom-scrollbar">
              <div v-if="loading" class="skeleton-container">
                <div class="skeleton-item" v-for="i in 5" :key="i"></div>
              </div>
              <div v-else-if="knowledgeData?.cleaned_knowledge" class="knowledge-list">
                <div v-for="(item, index) in knowledgeData.cleaned_knowledge" :key="index" class="knowledge-item animate-fade-in">
                  {{ item }}
                </div>
              </div>
              <div v-else class="empty-state">
                <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="8" y1="12" x2="16" y2="12"></line>
                </svg>
                <div>输入关键词开始搜索</div>
              </div>
            </div>
          </div>

          <!-- 图谱区域 -->
          <div class="card graph-section">
            <div class="card-header">
              <div class="card-title">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <circle cx="12" cy="12" r="4"></circle>
                  <line x1="21.17" y1="8" x2="12" y2="8"></line>
                  <line x1="3.95" y1="6.06" x2="8.54" y2="14"></line>
                  <line x1="10.88" y1="21.94" x2="15.46" y2="14"></line>
                </svg>
                <span>知识图谱</span>
              </div>
              <div v-if="graphData" class="graph-info">
                关键词: {{ graphData.query }}
              </div>
            </div>
            <div class="card-content graph-content custom-scrollbar">
              <div v-if="graphLoading" class="skeleton-container skeleton-graph">
                <div class="skeleton-circle"></div>
                <div class="skeleton-lines">
                  <div class="skeleton-line"></div>
                  <div class="skeleton-line"></div>
                  <div class="skeleton-line"></div>
                </div>
              </div>
              <div v-if="graphError" class="graph-error-message">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                  <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                {{ graphError }}
              </div>
              <div id="neovis-graph" ref="graphContainer" class="graph-container"></div>
              <div v-if="!keyword" class="graph-placeholder">
                <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="8" y1="12" x2="16" y2="12"></line>
                </svg>
                <div>搜索关键词查看知识图谱</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧试题区域 -->
        <div class="card quiz-section">
          <div class="card-header">
            <div class="card-title">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"></path>
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
              </svg>
              <span>试题</span>
            </div>
          </div>
          <div class="card-content custom-scrollbar">
            <div v-if="loading" class="skeleton-container">
              <div class="skeleton-item skeleton-question"></div>
              <div class="skeleton-options">
                <div class="skeleton-option" v-for="i in 4" :key="i"></div>
              </div>
            </div>
            <div v-else-if="knowledgeData?.question" class="question-container animate-fade-in">
              <div class="question-topic">{{ knowledgeData.question.topic }}</div>
              <div class="options-list">
                <div 
                  v-for="(option, key) in knowledgeData.question.options" 
                  :key="key"
                  class="option-item"
                  :class="{
                    'selected': selectedAnswer === key,
                    'correct': showAnswer && key === knowledgeData.question.answer,
                    'incorrect': showAnswer && selectedAnswer === key && key !== knowledgeData.question.answer
                  }"
                  @click="!showAnswer && checkAnswer(key)"
                >
                  <div class="option-marker">{{ key }}</div>
                  <div class="option-text">{{ option }}</div>
                </div>
              </div>
              <div v-if="showAnswer" class="answer-section animate-fade-in">
                <div class="answer-header">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                    <polyline points="22 4 12 14.01 9 11.01"></polyline>
                  </svg>
                  <span>答案解析</span>
                </div>
                <div class="answer">
                  <div class="answer-label">正确答案</div>
                  <div class="answer-content">{{ knowledgeData.question.answer }}</div>
                </div>
                <div class="parse">
                  <div class="parse-label">解析</div>
                  <div class="parse-content">{{ knowledgeData.question.parse }}</div>
                </div>
              </div>
            </div>
            <div v-else class="empty-state">
              <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="8" y1="12" x2="16" y2="12"></line>
              </svg>
              <div>搜索后显示相关试题</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/* 导入字体 */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap');

/* 重置默认样式 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  height: 100%;
  width: 100%;
  overflow: hidden;
  font-family: 'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
  color: #2c3e50;
  background-color: #f0f8ff;
}

#app {
  height: 100%;
  width: 100%;
}

.app-container {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: linear-gradient(135deg, #1976d2, #1565c0);
  color: white;
  padding: 15px 30px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  z-index: 10;
}

.logo {
  font-size: 20px;
  font-weight: 500;
  letter-spacing: 1px;
}

.main-content {
  flex: 1;
  padding: 20px;
  display: flex;
  flex-direction: column;
  max-width: 1300px;
  margin: 0 auto;
  width: 100%;
  min-height: 0;
  overflow: hidden;
}

/* 搜索区域样式 */
.search-section {
  background-color: white;
  padding: 15px 20px;
  margin-bottom: 20px;
  border-radius: 8px;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
}

.search-wrapper {
  display: flex;
  align-items: center;
  border: 1px solid #e0e7ff;
  border-radius: 6px;
  padding: 0 5px 0 15px;
  transition: all 0.3s;
  background-color: #f8faff;
}

.search-wrapper:focus-within {
  border-color: #1976d2;
  box-shadow: 0 0 0 3px rgba(25, 118, 210, 0.1);
}

.search-icon {
  color: #94a3b8;
  margin-right: 10px;
}

.search-input {
  flex: 1;
  height: 46px;
  padding: 0 10px;
  font-size: 15px;
  border: none;
  background: transparent;
  color: #334155;
}

.search-input:focus {
  outline: none;
}

.search-input::placeholder {
  color: #94a3b8;
}

.search-button {
  height: 38px;
  padding: 0 20px;
  background-color: #1976d2;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 80px;
}

.search-button:hover {
  background-color: #1565c0;
  transform: translateY(-1px);
}

.search-button:active {
  transform: translateY(1px);
}

.search-button.cancel-button {
  background-color: #ef4444;
}

.search-button.cancel-button:hover {
  background-color: #dc2626;
}

.error-message {
  color: #ef4444;
  margin-top: 8px;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 5px;
}

/* 进度条样式 */
.progress-container {
  margin-bottom: 20px;
  background-color: white;
  padding: 15px 20px;
  border-radius: 8px;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
  animation: pulse 2s infinite;
}

.progress-status {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  align-items: center;
}

.status-text {
  font-weight: 500;
  color: #1976d2;
}

.progress-percentage {
  font-weight: 700;
  color: #1976d2;
}

.progress-bar {
  height: 8px;
  background-color: #e0e7ff;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 10px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(to right, #1976d2, #64b5f6);
  border-radius: 4px;
  transition: width 0.5s ease;
}

.progress-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 13px;
  margin-top: 5px;
}

@keyframes pulse {
  0% {
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
  }
  50% {
    box-shadow: 0 3px 15px rgba(25, 118, 210, 0.15);
  }
  100% {
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
  }
}

/* 骨架屏 */
.skeleton-container {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.skeleton-item {
  height: 100px;
  background: linear-gradient(90deg, #f1f5f9 0%, #e2e8f0 50%, #f1f5f9 100%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 6px;
}

.skeleton-question {
  height: 120px;
}

.skeleton-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skeleton-option {
  height: 50px;
  background: linear-gradient(90deg, #f1f5f9 0%, #e2e8f0 50%, #f1f5f9 100%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 6px;
}

.skeleton-graph {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.skeleton-circle {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: linear-gradient(90deg, #f1f5f9 0%, #e2e8f0 50%, #f1f5f9 100%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  margin-bottom: 20px;
}

.skeleton-lines {
  width: 80%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skeleton-line {
  height: 10px;
  background: linear-gradient(90deg, #f1f5f9 0%, #e2e8f0 50%, #f1f5f9 100%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

/* 淡入动画 */
.animate-fade-in {
  animation: fadeIn 0.5s ease-in-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 内容区域样式 */
.content-section {
  display: flex;
  gap: 20px;
  flex: 1;
  min-height: 0;
}

.left-section {
  flex: 2;
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.card {
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.3s;
  width: 100%;
  box-sizing: border-box;
}

.card:hover {
  box-shadow: 0 6px 15px rgba(0, 0, 0, 0.1);
}

.card-header {
  padding: 15px 0;
  font-size: 16px;
  font-weight: 500;
  color: #1976d2;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #f8faff;
  width: 100%;
  box-sizing: border-box;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 20px;
}

.related-keywords {
  font-size: 12px;
  color: #64748b;
  font-weight: normal;
  background-color: #f1f5f9;
  padding: 3px 8px;
  border-radius: 4px;
  margin-right: 20px;
}

.card-content {
  flex: 1;
  padding: 20px;
  overflow: auto;
  position: relative;
  min-height: 100px;
  width: 100%;
  box-sizing: border-box;
}

.custom-scrollbar {
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 transparent;
  display: block;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: #cbd5e1;
  border-radius: 3px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: #94a3b8;
}

.knowledge-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;  /* 防止内容溢出 */
}

.knowledge-section .card-content {
  overflow-y: auto;  /* 确保垂直方向可以滚动 */
}

.quiz-section {
  flex: 1;
  max-width: 380px;
}

/* 知识点列表样式 */
.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.knowledge-item {
  padding: 12px 15px;
  background-color: #f8faff;
  border-radius: 6px;
  line-height: 1.6;
  border-left: 3px solid #1976d2;
  font-size: 14px;
}

/* 试题样式 */
.question-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.question-topic {
  font-size: 15px;
  line-height: 1.6;
  color: #334155;
  background-color: #f8faff;
  padding: 15px;
  border-radius: 6px;
  border-left: 3px solid #1976d2;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.option-item {
  display: flex;
  align-items: flex-start;
  padding: 10px;
  background-color: #f8faff;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #e5e7eb;
}

.option-marker {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background-color: #e0e7ff;
  color: #4f46e5;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 500;
  margin-right: 10px;
  flex-shrink: 0;
}

.option-text {
  flex: 1;
  padding-top: 4px;
}

.option-item:hover {
  background-color: #f0f7ff;
  transform: translateY(-1px);
}

.option-item.selected {
  border-color: #4f46e5;
  background-color: #f5f3ff;
}

.option-item.correct {
  background-color: #f0fdf4;
  border-color: #22c55e;
}

.option-item.correct .option-marker {
  background-color: #22c55e;
  color: white;
}

.option-item.incorrect {
  background-color: #fef2f2;
  border-color: #ef4444;
}

.option-item.incorrect .option-marker {
  background-color: #ef4444;
  color: white;
}

.answer-section {
  margin-top: 5px;
  padding: 15px;
  border-radius: 6px;
  background-color: #f8faff;
  border: 1px solid #e5e7eb;
}

.answer-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #1976d2;
  font-weight: 500;
  margin-bottom: 15px;
}

.answer, .parse {
  margin-bottom: 15px;
}

.answer-label, .parse-label {
  font-weight: 500;
  margin-bottom: 8px;
  color: #475569;
  font-size: 14px;
}

.answer-content {
  background-color: #effaf5;
  padding: 8px 12px;
  border-radius: 4px;
  color: #047857;
  font-weight: 500;
  display: inline-block;
}

.parse-content {
  line-height: 1.6;
  color: #475569;
  background-color: white;
  padding: 10px;
  border-radius: 4px;
  border: 1px solid #e5e7eb;
}

.empty-state {
  color: #94a3b8;
  text-align: center;
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  height: 100%;
}

/* 加载动画 */
.loading-container {
    display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 15px;
  height: 100%;
}

.loading-text {
  color: #64748b;
  font-size: 14px;
}

.loading-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #cbd5e1;
  border-top-color: #1976d2;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.loading-spinner.large {
  width: 40px;
  height: 40px;
  border-width: 3px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 响应式布局 */
@media screen and (max-width: 768px) {
  .app-header {
    padding: 12px 20px;
  }

  .main-content {
    padding: 15px;
  }

  .content-section {
    flex-direction: column;
  }

  .left-section {
    flex: none;
    height: 60%;
  }

  .quiz-section {
    flex: none;
    height: 40%;
    max-width: none;
  }

  .search-button {
    min-width: 70px;
  }
}

.graph-container {
  width: 100%;
  height: 500px;
  background-color: #fff;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
}

.graph-content {
  position: relative;
  height: 100%;
  min-height: 500px;
  padding: 0;
}

.graph-error-message {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background-color: #fef2f2;
  color: #ef4444;
  padding: 12px 20px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 10;
}

.graph-placeholder {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #94a3b8;
  z-index: 5;
}

.graph-section {
  flex: 1;
  min-height: 500px;
  display: flex;
  flex-direction: column;
}

.card-content {
  flex: 1;
  padding: 0;
  overflow: hidden;
  position: relative;
}
</style>
