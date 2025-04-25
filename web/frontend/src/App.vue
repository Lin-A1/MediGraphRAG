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
    categories: [
      { name: '知识点' },
      { name: '疾病' },
      { name: '症状' },
      { name: '药物' }
    ],
    force: {
      repulsion: 1500,
      edgeLength: [50, 200],
      gravity: 0.1,
      layoutAnimation: true
    },
    zoom: 1.2,
    roam: true,
    nodeScaleRatio: 0.7,
    draggable: true,
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
      width: 2,
      opacity: 0.7
    },
    itemStyle: {
      borderWidth: 2,
      borderColor: '#fff',
      shadowBlur: 10,
      shadowColor: 'rgba(0, 0, 0, 0.3)'
    },
    animation: true,
    animationDuration: 1000,
    animationEasingUpdate: 'quinticInOut'
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

  console.log("开始更新图表数据:", { nodes, links });

  // 确保数据格式正确
  const validNodes = Array.isArray(nodes) ? nodes : [];
  const validLinks = Array.isArray(links) ? links : [];

  console.log("有效数据:", { validNodes, validLinks });

  const option = {
    ...graphOptions,
    series: [{
      ...graphOptions.series[0],
      data: validNodes.map(node => ({
        ...node,
        itemStyle: {
          color: node.color || '#1976d2',
          opacity: node.isBaseNode ? 1 : 0.8,
          borderWidth: node.isBaseNode ? 3 : 2
        },
        symbolSize: node.isBaseNode ? 65 : (node.symbolSize || 50),
        label: {
          ...graphOptions.series[0].label,
          show: true
        }
      })),
      links: validLinks.map(link => ({
        ...link,
        lineStyle: {
          ...graphOptions.series[0].lineStyle,
          curveness: Math.random() * 0.3
        },
        label: {
          show: true,
          formatter: link.label,
          fontSize: 10,
          color: '#64748b',
          position: 'middle'
        }
      }))
    }]
  };

  // 如果没有数据，显示提示信息
  if (validNodes.length === 0) {
    option.graphic = [{
      type: 'text',
      left: 'center',
      top: 'middle',
      style: {
        text: '暂无相关图谱数据',
        fontSize: 14,
        fill: '#64748b'
      }
    }];
  } else {
    option.graphic = [];
  }

  console.log("设置图表选项:", option);
  graphChart.value.setOption(option, true);

  // 如果有数据，调整布局
  if (validNodes.length > 0) {
    setTimeout(() => {
      graphChart.value?.setOption({
        series: [{
          force: {
            layoutAnimation: true,
            repulsion: validNodes.length < 5 ? 300 : 1500, // 根据节点数量调整斥力
            edgeLength: validNodes.length < 5 ? [50, 150] : [50, 200] // 根据节点数量调整边长度
          },
          nodeScaleRatio: validNodes.length < 5 ? 0.8 : 0.7
        }]
      });
    }, 10);
  }
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

    // 确保数据格式正确
    const nodes = Array.isArray(data.nodes) ? data.nodes : [];
    const links = Array.isArray(data.links) ? data.links : [];

    console.log("处理后的数据:", { nodes, links });

    // 更新图谱数据状态
    if (!graphData.value) {
      // 第一次搜索，直接赋值
      graphData.value = {
        query,
        timestamp: Date.now(),
        nodes,
        links
      };
    } else {
      // 后续搜索，合并数据
      const existingNodes = new Map(graphData.value.nodes.map(node => [node.name, node]));
      const existingLinks = new Set(
        graphData.value.links.map(link => `${link.source}-${link.label}-${link.target}`)
      );

      // 添加新节点
      nodes.forEach(node => {
        if (!existingNodes.has(node.name)) {
          graphData.value.nodes.push(node);
        }
      });

      // 添加新连接
      links.forEach(link => {
        const linkKey = `${link.source}-${link.label}-${link.target}`;
        if (!existingLinks.has(linkKey)) {
          graphData.value.links.push(link);
        }
      });

      // 更新查询关键词
      graphData.value.query = graphData.value.query + '、' + query;
      graphData.value.timestamp = Date.now();
    }

    console.log("更新后的图谱数据状态:", graphData.value);

    // 更新图表显示
    updateGraphData(graphData.value.nodes, graphData.value.links);

  } catch (err) {
    console.error("图谱查询失败:", err);
    graphError.value = "图谱数据查询失败: " + err.message;
    // 即使出错也尝试更新图表为空状态
    updateGraphData([], []);
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

// 添加重置图谱的函数
const resetGraph = () => {
  if (graphChart.value) {
    console.log("重置图谱...");
    graphChart.value.setOption({
      series: [{
        data: [],
        links: []
      }],
      graphic: [] // 清除可能存在的提示信息
    });
  }
  graphData.value = null; // 清空图谱数据状态
  graphError.value = ''; // 清除错误信息
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
    
    // 重置图谱
    resetGraph();
    
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
      try {
        const keywordsToSearch = [keyword.value, ...data.related_keywords];
        const uniqueKeywords = [...new Set(keywordsToSearch)]; // 去重

        console.log("开始搜索图谱，关键词:", uniqueKeywords);
        for (const kw of uniqueKeywords) {
          await searchGraphByKeyword(kw);
        }
      } catch (graphErr) {
        console.error('图谱更新失败:', graphErr);
        graphError.value = '图谱更新失败: ' + graphErr.message;
      }
    } else {
      // 如果没有相关关键词，至少搜索主关键词
      console.log("开始搜索图谱，关键词:", [keyword.value]);
      await searchGraphByKeyword(keyword.value);
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
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
}

.app-header {
  background: linear-gradient(135deg, #1e40af, #1e3a8a);
  color: white;
  padding: 18px 30px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
  z-index: 10;
  position: relative;
}

.logo {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 1.2px;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
}

.main-content {
  flex: 1;
  padding: 25px;
  display: flex;
  flex-direction: column;
  max-width: 1800px;
  margin: 0 auto;
  width: 100%;
  min-height: 0;
  overflow: hidden;
  gap: 20px;
}

/* 搜索区域美化 */
.search-section {
  background-color: white;
  padding: 20px;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
}

.search-section:hover {
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.08);
}

.search-wrapper {
  display: flex;
  align-items: center;
  border: 2px solid #e0e7ff;
  border-radius: 12px;
  padding: 0 8px 0 20px;
  transition: all 0.3s;
  background-color: #f8faff;
}

.search-wrapper:focus-within {
  border-color: #1e40af;
  box-shadow: 0 0 0 4px rgba(30, 64, 175, 0.1);
}

.search-icon {
  color: #94a3b8;
  margin-right: 10px;
}

.search-input {
  flex: 1;
  height: 52px;
  padding: 0 16px;
  font-size: 16px;
  border: none;
  background: transparent;
  color: #1e293b;
}

.search-input:focus {
  outline: none;
}

.search-input::placeholder {
  color: #94a3b8;
}

.search-button {
  height: 44px;
  padding: 0 28px;
  background: linear-gradient(135deg, #1e40af, #1e3a8a);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 100px;
}

.search-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(30, 64, 175, 0.25);
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
  margin-bottom: 25px;
  background-color: white;
  padding: 25px;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
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
  height: 10px;
  background-color: #e0e7ff;
  border-radius: 5px;
  overflow: hidden;
  margin: 20px 0;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(to right, #1e40af, #3b82f6);
  border-radius: 5px;
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
  gap: 15px;
  flex: 1;
  min-height: 0;
}

.left-section {
  flex: 2.5;
  display: flex;
  flex-direction: column;
  gap: 15px;
  min-width: 0;
}

.card {
  background-color: white;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.3s ease;
  width: 100%;
  box-sizing: border-box;
}

.card:hover {
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.card-header {
  padding: 15px 20px;
  font-size: 18px;
  font-weight: 600;
  color: #1e40af;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(to right, #f8faff, #f0f7ff);
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
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
  padding: 25px;
  overflow: auto;
  position: relative;
  min-height: 120px;
}

.custom-scrollbar {
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 transparent;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 8px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: #cbd5e1;
  border-radius: 4px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: #94a3b8;
}

.knowledge-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  max-height: 400px;  /* 限制最大高度 */
}

.knowledge-section .card-content {
  overflow-y: auto;
  max-height: 350px;  /* 限制内容区域最大高度 */
}

.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: 8px;  /* 进一步减小间距 */
}

.knowledge-item {
  padding: 10px 14px;  /* 进一步减小内边距 */
  background-color: #f8faff;
  border-radius: 6px;
  line-height: 1.4;
  border-left: 2px solid #1e40af;
  transition: all 0.3s ease;
  font-size: 13px;
  color: #334155;
  margin-bottom: 2px;  /* 添加底部间距 */
}

.knowledge-item:hover {
  background-color: #f0f7ff;
  transform: translateX(1px);
  box-shadow: 0 1px 4px rgba(30, 64, 175, 0.1);
}

.quiz-section {
  flex: 1;
  max-width: 460px;
}

/* 试题样式 */
.question-container {
  display: flex;
  flex-direction: column;
  gap: 25px;
}

.question-topic {
  font-size: 16px;
  line-height: 1.7;
  color: #334155;
  background-color: #f8faff;
  padding: 20px;
  border-radius: 12px;
  border-left: 4px solid #1e40af;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.option-item {
  display: flex;
  align-items: flex-start;
  padding: 16px;
  background-color: #f8faff;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 2px solid #e5e7eb;
}

.option-item:hover {
  background-color: #f0f7ff;
  transform: translateY(-2px);
  border-color: #1e40af;
  box-shadow: 0 4px 12px rgba(30, 64, 175, 0.1);
}

.option-marker {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background-color: #e0e7ff;
  color: #1e40af;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  margin-right: 16px;
  flex-shrink: 0;
  transition: all 0.3s ease;
}

.option-text {
  flex: 1;
  padding-top: 4px;
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

/* 响应式布局优化 */
@media screen and (max-width: 768px) {
  .main-content {
    padding: 15px;
  }

  .content-section {
    flex-direction: column;
    gap: 15px;
  }

  .left-section {
    flex: none;
    height: auto;
  }

  .quiz-section {
    flex: none;
    height: auto;
    max-width: none;
  }

  .search-button {
    min-width: 90px;
    padding: 0 20px;
  }
}

.graph-container {
  width: 100%;
  height: 520px;
  background-color: #fff;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
}

.graph-content {
  position: relative;
  height: 100%;
  min-height: 520px;
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
  background-color: white;
  border-radius: 12px;
  overflow: hidden;
}

.card-content {
  flex: 1;
  padding: 0;
  overflow: hidden;
  position: relative;
}
</style>
