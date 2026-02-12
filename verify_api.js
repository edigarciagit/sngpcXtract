const https = require('https');

const options = {
  hostname: 'consultas.anvisa.gov.br',
  path: '/api/consulta/medicamento/produtos/?column=&count=10&filter%5Batc%5D=A&filter%5BcheckNotificado%5D=false&filter%5BcheckRegistrado%5D=true&filter%5BsituacaoRegistro%5D=V&order=asc&page=1',
  method: 'GET',
  headers: {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Authorization': 'Guest',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Cookie': 'cf_clearance=Wl9W63kmLKcEHFRcRIifjAxQnzZGk9l7cMNCn7qwbgs-1770818408-1.2.1.1-hnhHqMsrVkXctFEIwokiCxxx1TOw1AlkUZbkQQPHOU3RDC6B4uaGW5lOt5lUiH6qbKTMK9cF2TkGRTEP2DBp2YkVKdNv4gmOaWmv7BjdG9qH3JALYMpYgXUfAgqM9qdgcjjxdqiaVolptb3CAPPiheRG5mp7qu97eQm57GwEtOV9zXrajlxQ9HcPkGi8ojCS5VFIchOn5IJo.PBmT1QYklNjBgAF2D75aNOZYAB6fIo; dtCookiew5fdz9p6=v_4_srv_6_sn_6636DBC9C9DE1457AA5EE03FEAE1E945_perc_100000_ol_0_mul_1_app-3A70d59aa21861f7ba_0; _cfuvid=FMIutvvvTPwM2z57hiH.rwS_Wn7HDN514WBGyhnQI40-1770901496.6069074-1.0.1.1-HtS6mPNTloF6vMXGBM48Pq_KQzce_1_ipFYr0Dx_PW8',
    'Host': 'consultas.anvisa.gov.br',
    'Pragma': 'no-cache',
    'Referer': 'https://consultas.anvisa.gov.br/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'x-dtpc': '6$301373505_789h54vPROKIOACELUREAUVUTCWDGTBUJGGKAAK-0e0',
    'x-dtreferer': 'https://consultas.anvisa.gov.br/'
  }
};

const req = https.request(options, (res) => {
  console.log(`STATUS: ${res.statusCode}`);
  let data = '';

  res.on('data', (chunk) => {
    data += chunk;
  });

  res.on('end', () => {
    console.log('BODY:', data.substring(0, 500) + '...');
  });
});

req.on('error', (e) => {
  console.error(`problem with request: ${e.message}`);
});

req.end();
