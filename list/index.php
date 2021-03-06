<?php
	// Custom ETag Handling
	$etag = '"' . md5_file(__FILE__) . (isset($_GET['frame']) ? 'F"' : '"');
	if (trim($_SERVER['HTTP_IF_NONE_MATCH']) == $etag) {
		header('HTTP/1.1 304 Not Modified');
		die();
	}
	header('ETag: ' . $etag);
?>
<!DOCTYPE html>
<html lang="en">
	<head>
		<title>Video List</title>
		<meta charset="UTF-8">
		<base target="_parent">
		<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/font-awesome/4.5.0/css/font-awesome.min.css">
		<link rel="stylesheet" type="text/css" href="../CSS/page.css">
		<link rel="stylesheet" type="text/css" href="../CSS/list.css">
<?php if(isset($_GET['frame'])) echo '		<link rel="stylesheet" type="text/css" href="../CSS/frame.css">'; ?>
		<meta name="viewport" content="width=device-width, initial-scale=1">
		<script src="../JS/list.js"></script>
	</head>
	<body>
		<header>
			<div>
				<h1>Video List</h1>
				<?php include '../hub/navbar'; ?>
			</div>
		</header>
		<main>
			<div id="playlist" hidden>
				<p class="playlistTop">0 Videos in Playlist</p>
				<p class="playlistBot"><span>Edit Playlist</span><span></span><span>Start Playlist</span></p>
			</div>

			<?php
			// Load names.php and count videos/series

			include_once '../names.php';

			$videosnumber = 0;
			foreach ($names as $videos) $videosnumber += count($videos);
			$seriesnumber = count($names);

			echo '<p>We currently serve <span class="count">' . $videosnumber . '</span> videos from <span class="count">' . $seriesnumber . '</span> series.</p>';
			?>

			<label>
				<a id="searchURL" href="">Search:</a>
				<input id="searchbox" type="text" placeholder="Series name..." autofocus>
			</label>
			<br>
			<p id="regex"><span>(press tab while typing to enable RegEx in search)</span></p>
			<br>

			<div id="NoResultsMessage" hidden>
				<p>We could not find any shows matching your search query.</p>
				<ol>
					<li>Is it spelled correctly?</li>
					<li>Have you tried using the Japanese title?</li>
					<li>Have you tried using the English title?</li>
				</ol>
				<p>If you still can't find the video you are looking for, we probably don't have it yet.</p>
			</div>

			<?php
			include_once '../backend/includes/helpers.php';

			// Output list of videos
			foreach ($names as $series => $video_array) {

				$html = '';
				foreach ($video_array as $title => $data) {
					// Skip Easter Eggs
					if (isset($data['egg']) && $data['egg']) continue;

					// Generate HTML for each video
					$html .= '	<i class="fa fa-plus" data-file="' . htmlspecialchars($data['file']) . '" data-mime="' . htmlspecialchars(json_encode($data['mime'])) . '"';
					if (array_key_exists('song', $data)) $html .= ' data-songtitle="' . htmlspecialchars($data['song']['title']) . '" data-songartist="' . htmlspecialchars($data['song']['artist']) . '"';
					if (array_key_exists('subtitles', $data)) $html .= ' data-subtitles="' . htmlspecialchars($data['subtitles']) . '"';
					$html .= '></i>' . PHP_EOL;
					$html .= '	<a href="../?video=' . filenameToIdentifier($data['file']) . '">' . $title . '</a>' . PHP_EOL;
					$html .= '	<br>' . PHP_EOL;
				}

				// If any video data HTML was generated, output the series name and the HTML
				if ($html) {
					echo '<div class="series">' . $series . '<div>' . PHP_EOL;
					echo $html;
					echo '</div></div>' . PHP_EOL;
				}
			}
			?>
		</main>

		<?php include_once '../backend/includes/botnet.html'; ?>
	</body>
</html>
