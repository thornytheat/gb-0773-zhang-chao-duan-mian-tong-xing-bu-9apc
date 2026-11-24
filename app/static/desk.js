const sample = document.querySelector('#sample');
sample.addEventListener('change', () => document.querySelector('input[name=run]')?.remove());
document.querySelector('#print-book').addEventListener('click', () => window.print());

async function post(url, body) {
  const res = await fetch(url, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || '请求失败');
  return data;
}

const rerun = document.querySelector('#rerun');
rerun?.addEventListener('click', async () => {
  const feedback = document.querySelector('#feedback');
  rerun.disabled = true;
  feedback.textContent = '复算中…';
  try {
    const data = await post(`/api/journal/${rerun.dataset.run}/rerun`, {});
    feedback.textContent = data.reused ? '复算一致，沿用原簿' : '新簿已归档';
  } catch (error) {
    feedback.textContent = `${error.message}，请重试。`;
  } finally { rerun.disabled = false; }
});

const amend = document.querySelector('#amend-run');
amend?.addEventListener('click', async () => {
  const feedback = document.querySelector('#amend-feedback');
  amend.disabled = true;
  feedback.textContent = '重算中…';
  try {
    const data = await post(`/api/journal/${amend.dataset.run}/rerun`,
      {speeds: document.querySelector('#speeds').value});
    if (!data.reused) location.href = `/desk/journal?run=${data.run_id}`;
    else feedback.textContent = '结论一致，沿用原簿';
  } catch (error) {
    feedback.textContent = `${error.message}，请重试。`;
  } finally { amend.disabled = false; }
});
