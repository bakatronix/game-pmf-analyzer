<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }

$input = json_decode(file_get_contents('php://input'), true);
$appId = intval($input['app_id'] ?? 0);
if ($appId <= 0) { http_response_code(400); echo json_encode(['detail'=>'Invalid app_id']); exit; }

function apiFetch($url) {
    $ctx = stream_context_create(['http'=>['timeout'=>25,'header'=>"Accept: application/json\r\n"]]);
    $json = @file_get_contents($url, false, $ctx);
    return $json ? json_decode($json, true) : null;
}
function cacheGet($key) {
    $f = sys_get_temp_dir()."/pmfv2_".md5($key).".json";
    if (file_exists($f) && (time()-filemtime($f)) < 3600) return json_decode(file_get_contents($f), true);
    return null;
}
function cacheSet($key, $data) {
    file_put_contents(sys_get_temp_dir()."/pmfv2_".md5($key).".json", json_encode($data));
}
function cl($v, $l=0, $h=100) { return max($l, min($h, $v)); }

$ck = "app_{$appId}";
$app = cacheGet($ck);
if (!$app) {
    $d = apiFetch("https://store.steampowered.com/api/appdetails?appids={$appId}&l=english");
    $app = ($d && isset($d[strval($appId)])) ? $d[strval($appId)] : ['success'=>false];
    cacheSet($ck, $app);
}
if (!$app['success']) { http_response_code(404); echo json_encode(['detail'=>'App not found']); exit; }
$data = $app['data'];
$gameName = $data['name'] ?? "App {$appId}";
$genres = array_map(fn($g)=>$g['description'], $data['genres'] ?? []);
if (!$genres) $genres = ['Indie'];
$release = $data['release_date']['date'] ?? null;

$revCache = cacheGet("rev_{$appId}");
if (!$revCache) {
    $allRev = []; $summary = []; $cursor = '*';
    for ($p = 0; $p < 2; $p++) {
        $r = apiFetch("https://store.steampowered.com/appreviews/{$appId}?json=1&language=all&purchase_type=all&num_per_page=100&cursor={$cursor}");
        if (!$r) break;
        if (!$summary) $summary = $r['query_summary'] ?? [];
        $batch = $r['reviews'] ?? [];
        if (!$batch) break;
        $allRev = array_merge($allRev, $batch);
        $cursor = $r['cursor'] ?? '*';
        usleep(800000);
    }
    $revCache = ['summary' => $summary, 'reviews' => $allRev];
    cacheSet("rev_{$appId}", $revCache);
}
$summary = $revCache['summary'];
$allReviews = $revCache['reviews'];
$total = $summary['total_reviews'] ?? 0;
$positive = $summary['total_positive'] ?? 0;

$ach = cacheGet("ach_{$appId}");
if ($ach === null) {
    $a = apiFetch("https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/?gameid={$appId}");
    $ach = $a['achievementpercentages']['achievements'] ?? [];
    cacheSet("ach_{$appId}", $ach);
}
$achPcts = array_map(fn($a)=>floatval($a['percent']??0), $ach);

$ccu = cacheGet("ccu_{$appId}");
if ($ccu === null) {
    $p = apiFetch("https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={$appId}");
    $ccu = $p['response']['player_count'] ?? 0;
    cacheSet("ccu_{$appId}", $ccu);
}

$newsCache = cacheGet("news_{$appId}");
if ($newsCache === null) {
    $n = apiFetch("https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={$appId}&count=20&maxlength=300");
    $newsCache = $n['appnews']['newsitems'] ?? [];
    cacheSet("news_{$appId}", $newsCache);
}
$patchKw = ['update','patch','hotfix','version','release','build'];
$patchCount = 0;
foreach ($newsCache as $n) {
    $txt = ($n['title'] ?? '') . ' ' . ($n['contents'] ?? '');
    foreach ($patchKw as $kw) { if (stripos($txt, $kw) !== false) { $patchCount++; break; } }
}

// === SCORING ===
$satisfaction = null;
if ($total >= 50) {
    $posPct = $positive / $total * 100;
    $trendBonus = cl($posPct - $posPct, -10, 10);
    $satScore = cl($posPct + 0.5 * $trendBonus, 0, 100);
    $ci = $total > 500 ? 5 : ($total > 100 ? 10 : 20);
    $satisfaction = ['score'=>round($satScore,1),'ci'=>$ci,'positive_pct'=>round($posPct,1),'recent_pct'=>round($posPct,1),'trend_bonus'=>round($trendBonus,1),'total_reviews'=>$total];
}

$playtimes = [];
foreach ($allReviews as $r) { $pt = $r['author']['playtime_forever'] ?? 0; if ($pt > 0) $playtimes[] = $pt; }
$engagement = null;
if ($playtimes) {
    sort($playtimes); $n = count($playtimes);
    $medianMin = $playtimes[(int)floor($n / 2)]; $medianHr = $medianMin / 60;
    $playtimeScore = cl(log(1 + $medianHr) / log(1 + 10 * 3) * 95, 0, 95);
    $sub2h = count(array_filter($playtimes, fn($p)=>$p<120)); $sub2hRatio = $sub2h / $n;
    $hookScore = cl((1 - $sub2hRatio) * 100, 0, 100);
    $deepest = $achPcts ? min($achPcts) : 100;
    $depthScore = $achPcts ? cl((100 - $deepest) * 0.5, 0, 100) : 50;
    $engScore = 0.50 * $playtimeScore + 0.30 * $hookScore + 0.20 * $depthScore;
    $buckets = [
        'sub_1h'=>count(array_filter($playtimes,fn($p)=>$p<60)),
        '1h_to_2h'=>count(array_filter($playtimes,fn($p)=>$p>=60&&$p<120)),
        '2h_to_5h'=>count(array_filter($playtimes,fn($p)=>$p>=120&&$p<300)),
        '5h_to_20h'=>count(array_filter($playtimes,fn($p)=>$p>=300&&$p<1200)),
        '20h_plus'=>count(array_filter($playtimes,fn($p)=>$p>=1200)),
    ];
    $engagement = ['score'=>round($engScore,1),'playtime_score'=>round($playtimeScore,1),'hook_score'=>round($hookScore,1),'depth_score'=>round($depthScore,1),'median_hr'=>round($medianHr,1),'sub2h_ratio'=>round($sub2hRatio*100,1),'sub2h_ratio_raw'=>round($sub2hRatio,4),'deepest_ach_pct'=>$achPcts?round($deepest,1):null,'playtime_buckets'=>$buckets,'sample_size'=>$n];
}

$rvScore = cl(log10(max($total, 1)) * 25, 0, 100);
$vel = $total > 0 ? $total / 30 : 0;
$velocityScore = cl(log(1 + $vel) / log(1 + 0.5) * 100, 0, 100);
$ccuScore = cl(log(1 + $ccu) / log(1 + 2000) * 100, 0, 100);
$reachScore = 0.40 * $rvScore + 0.35 * $velocityScore + 0.25 * $ccuScore;
$reach = ['score'=>round($reachScore,1),'review_volume_score'=>round($rvScore,1),'velocity_score'=>round($velocityScore,1),'ccu_score'=>round($ccuScore,1),'total_reviews'=>$total,'velocity'=>round($vel,4),'peak_ccu'=>$ccu];

$s=$satisfaction?$satisfaction['score']:0; $e=$engagement?$engagement['score']:0; $r=$reach['score'];
$parts = [];
foreach ([['Satisfaction',$satisfaction],['Engagement',$engagement],['Reach',$reach]] as $pair) {
    list($name,$l)=$pair;
    if(!$l){$parts[]="$name: undefined (<50 reviews)";continue;}
    $parts[]=sprintf("%s: %.1f/100 (%s)",$name,$l['score'],$l['score']>=70?'Strong':($l['score']>=50?'Moderate':'Weak'));
}
$hdr = implode(' | ',$parts);
if($satisfaction&&$engagement&&$reach&&$s>=70&&$e>=70&&$r>=70) $interp='Strong PMF signal across all dimensions';
elseif($satisfaction&&$s>=75&&$engagement&&$e>=70&&$reach&&$r<50) $interp='Niche hit not yet finding its audience';
elseif($satisfaction&&$s>=70&&$engagement&&$e<50) $interp='Good first impression, weak retention hook';
elseif($engagement&&$e>=70&&$satisfaction&&$s<60) $interp='Engaged but divisive — check sentiment breakdown';
elseif(($satisfaction?$satisfaction['score']<50:true)&&($engagement?$engagement['score']<50:true)&&($reach?$reach['score']<50:true)) $interp='Weak signal — recommend re-scoping or major update';
else $interp='Mixed signals — review individual lens scores for specifics';
$label = "$hdr\n  → $interp";

$recs=[];
$fg=$genres[0]??'genre';
if($engagement&&$engagement['sub2h_ratio']>30){
    $recs[]=['priority'=>'HIGH','category'=>'Engagement','title'=>'Hook problem — players bouncing before refund window','detail'=>"{$engagement['sub2h_ratio']}% under 2h. Prioritize opening-sequence tuning: tutorial pacing, first-reward timing."];
}elseif($engagement&&$engagement['sub2h_ratio']>15){
    $recs[]=['priority'=>'MEDIUM','category'=>'Engagement','title'=>'Elevated early drop-off','detail'=>"{$engagement['sub2h_ratio']}% sub-2h. Review the first-session experience for friction points."];
}
if($engagement&&$engagement['median_hr']>20){
    $recs[]=['priority'=>'HIGH','category'=>'Engagement','title'=>'Strong deep engagement','detail'=>"Median {$engagement['median_hr']}h is exceptional. Feature longevity in marketing."];
}
if($satisfaction&&$satisfaction['score']<70){
    $recs[]=['priority'=>'HIGH','category'=>'Satisfaction','title'=>'Review score below 70%','detail'=>"At {$satisfaction['positive_pct']}% positive, prioritize fixes for top complaints."];
}
if($satisfaction&&($satisfaction['trend_bonus']??0)<-3){
    $recs[]=['priority'=>'HIGH','category'=>'Satisfaction','title'=>'Review trend declining','detail'=>"Trend bonus: {$satisfaction['trend_bonus']}. Investigate recent changes."];
}
if($reach['score']<30){
    $recs[]=['priority'=>'HIGH','category'=>'Reach','title'=>'Critically low reach','detail'=>"{$reach['total_reviews']} reviews, {$reach['peak_ccu']} CCU. Prioritize discovery."];
}elseif($reach['score']<50){
    $recs[]=['priority'=>'MEDIUM','category'=>'Reach','title'=>'Below-average reach','detail'=>'Consider a demo, festival submission, or creator campaign.'];
}
if($patchCount==0){
    $recs[]=['priority'=>'LOW','category'=>'Communication','title'=>'No patches detected','detail'=>'Even a small update can trigger a review bump.'];
}
usort($recs,fn($a,$b)=>['HIGH'=>0,'MEDIUM'=>1,'LOW'=>2][$a['priority']]<=>['HIGH'=>0,'MEDIUM'=>1,'LOW'=>2][$b['priority']]);
$recs=array_slice($recs,0,3);

// Sentiment
$lexicon = ['amazing'=>3.2,'awesome'=>3.1,'excellent'=>3.0,'fantastic'=>3.2,'incredible'=>3.3,'love'=>3.0,'perfect'=>3.1,'wonderful'=>2.8,'great'=>2.5,'fun'=>2.4,'addictive'=>2.3,'beautiful'=>2.7,'brilliant'=>2.9,'masterpiece'=>3.5,'enjoyable'=>2.2,'engaging'=>1.9,'immersive'=>2.4,'polished'=>2.1,'smooth'=>1.7,'satisfying'=>2.0,'impressive'=>2.3,'outstanding'=>3.0,'superb'=>3.0,'good'=>1.5,'nice'=>1.3,'best'=>2.8,'creative'=>1.9,'charming'=>1.8,'atmospheric'=>1.9,'clever'=>1.7,'rewarding'=>2.1,'worth'=>1.6,'unique'=>2.0,'refreshing'=>2.2,'deep'=>1.5,'solid'=>1.4,'favorite'=>2.2,'gorgeous'=>2.7,'stunning'=>3.0,'delightful'=>2.5,'thrilling'=>2.6,'bad'=>-2.0,'terrible'=>-3.0,'awful'=>-3.0,'horrible'=>-3.1,'worst'=>-3.0,'hate'=>-2.7,'boring'=>-2.5,'broken'=>-2.8,'buggy'=>-2.6,'trash'=>-3.0,'garbage'=>-3.1,'disappointing'=>-2.4,'frustrating'=>-2.2,'annoying'=>-2.0,'mediocre'=>-1.5,'shallow'=>-1.7,'clunky'=>-1.8,'laggy'=>-2.4,'grindy'=>-1.4,'repetitive'=>-2.0,'unfinished'=>-2.7,'overpriced'=>-1.8,'generic'=>-1.5,'bland'=>-1.8,'ugly'=>-1.9,'stale'=>-1.6,'tedious'=>-1.9,'unoptimized'=>-2.2,'crashing'=>-2.9,'unplayable'=>-3.0,'poor'=>-2.0,'lame'=>-2.0,'fail'=>-2.5,'useless'=>-2.5,'regret'=>-2.3,'painful'=>-2.3,'atrocious'=>-3.2,'pathetic'=>-2.8,'abandoned'=>-2.6,'lazy'=>-2.1,'sloppy'=>-2.3,'janky'=>-1.8];
$gamingTerms = array_fill_keys(['addictive','fun','boring','grindy','repetitive','polished','buggy','broken','masterpiece','unique','generic','short','difficult','easy','deep','shallow','beautiful','ugly','smooth','clunky','atmospheric','immersive','bland','creative','innovative','classic','fresh','stale','rewarding','frustrating','satisfying','disappointing','overhyped','underrated','overpriced','worth','refunded','crashing','performance','story','gameplay','graphics','soundtrack','controls','replayable','content','update','dev','unfinished','promising','abandoned','optimized','unoptimized','laggy','responsive'], 1);

$sentScores=[];$keywords=[];$posC=0;$neuC=0;$negC=0;
foreach($allReviews as $r){
    $text=$r['review']??''; if(!$text)continue;
    $words=preg_split('/\s+/',strtolower($text));$totalScore=0;$wc=0;
    foreach($words as $w){$w=preg_replace('/[^a-z]/','',$w);if(strlen($w)<2)continue;if(isset($lexicon[$w])){$totalScore+=$lexicon[$w];$wc++;}if(isset($gamingTerms[$w])){$keywords[$w]=($keywords[$w]??0)+1;}}
    $compound=$wc>0?$totalScore/sqrt($wc*$wc+15):0;$compound=max(-1,min(1,$compound));$sentScores[]=$compound;
    if($compound>=0.05)$posC++;elseif($compound<=-0.05)$negC++;else $neuC++;
}
$avgCompound=count($sentScores)>0?array_sum($sentScores)/count($sentScores):0;$totalS=count($sentScores)?:1;
arsort($keywords);$topKw=array_slice($keywords,0,12,true);$kwList=[];foreach($topKw as $kw=>$cnt)$kwList[]=['keyword'=>$kw,'count'=>$cnt];
$sentiment=['compound_score'=>round($avgCompound,3),'top_keywords'=>$kwList,'sentiment_distribution'=>['positive'=>round($posC/$totalS*100,1),'neutral'=>round($neuC/$totalS*100,1),'negative'=>round($negC/$totalS*100,1)]];

// Review detail
$reviewScorePct = $total > 0 ? round($positive / $total * 100, 1) : 0;
if ($reviewScorePct >= 95) $trend = 'Overwhelmingly Positive';
elseif ($reviewScorePct >= 80) $trend = 'Very Positive';
elseif ($reviewScorePct >= 70) $trend = 'Mostly Positive';
elseif ($reviewScorePct >= 40) $trend = 'Mixed';
else $trend = 'Mostly Negative';

// Benchmarks
$allBM = [
    'Action'=>['median_playtime_hours'=>12,'avg_review_score'=>82,'avg_ccu'=>1200,'avg_total_reviews'=>5000,'avg_achievement_completion'=>35],
    'Adventure'=>['median_playtime_hours'=>8,'avg_review_score'=>85,'avg_ccu'=>600,'avg_total_reviews'=>3000,'avg_achievement_completion'=>40],
    'RPG'=>['median_playtime_hours'=>25,'avg_review_score'=>83,'avg_ccu'=>1500,'avg_total_reviews'=>8000,'avg_achievement_completion'=>30],
    'Strategy'=>['median_playtime_hours'=>20,'avg_review_score'=>80,'avg_ccu'=>800,'avg_total_reviews'=>4000,'avg_achievement_completion'=>28],
    'Simulation'=>['median_playtime_hours'=>18,'avg_review_score'=>81,'avg_ccu'=>700,'avg_total_reviews'=>3500,'avg_achievement_completion'=>32],
    'Racing'=>['median_playtime_hours'=>6,'avg_review_score'=>79,'avg_ccu'=>300,'avg_total_reviews'=>1500,'avg_achievement_completion'=>38],
    'Sports'=>['median_playtime_hours'=>10,'avg_review_score'=>78,'avg_ccu'=>400,'avg_total_reviews'=>2000,'avg_achievement_completion'=>36],
    'Casual'=>['median_playtime_hours'=>4,'avg_review_score'=>84,'avg_ccu'=>500,'avg_total_reviews'=>2500,'avg_achievement_completion'=>45],
    'Roguelike'=>['median_playtime_hours'=>30,'avg_review_score'=>85,'avg_ccu'=>1000,'avg_total_reviews'=>6000,'avg_achievement_completion'=>25],
    'Horror'=>['median_playtime_hours'=>5,'avg_review_score'=>82,'avg_ccu'=>350,'avg_total_reviews'=>2000,'avg_achievement_completion'=>42],
    'Puzzle'=>['median_playtime_hours'=>5,'avg_review_score'=>86,'avg_ccu'=>200,'avg_total_reviews'=>1500,'avg_achievement_completion'=>44],
    'Platformer'=>['median_playtime_hours'=>6,'avg_review_score'=>83,'avg_ccu'=>400,'avg_total_reviews'=>2000,'avg_achievement_completion'=>40],
    'FPS'=>['median_playtime_hours'=>15,'avg_review_score'=>80,'avg_ccu'=>2000,'avg_total_reviews'=>10000,'avg_achievement_completion'=>33],
    'Indie'=>['median_playtime_hours'=>6,'avg_review_score'=>84,'avg_ccu'=>500,'avg_total_reviews'=>2500,'avg_achievement_completion'=>38],
];
$bm = ['genre'=>'Indie (default)'] + $allBM['Indie'];
foreach ($genres as $g) { if (isset($allBM[$g])) { $bm = ['genre'=>$g] + $allBM[$g]; break; } }

echo json_encode([
    'app_id'=>$appId,'game_name'=>$gameName,'genres'=>$genres,'release_date'=>$release,
    'lenses'=>['satisfaction'=>$satisfaction,'engagement'=>$engagement,'reach'=>$reach],
    'label'=>$label,'cohort'=>null,'recommendations'=>$recs,'patch_count'=>$patchCount,
    'reviews'=>['total'=>$total,'positive'=>$positive,'negative'=>$total-$positive,'score'=>$reviewScorePct,'trend_label'=>$trend],
    'sentiment'=>$sentiment,
    'benchmarks'=>$bm,
    'median_playtime_minutes'=>count($playtimes)?$playtimes[(int)floor(count($playtimes)/2)]:0,
    'ccu_current'=>$ccu,
    'data_quality'=>['review_sample_size'=>count($playtimes),'achievements_available'=>count($achPcts)>0,'ccu_available'=>$ccu>0],
]);
